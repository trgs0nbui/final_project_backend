import logging

from django.contrib.auth import authenticate
from django.contrib.auth.backends import ModelBackend
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from rest_framework.exceptions import ValidationError, AuthenticationFailed

from .models import User

logger = logging.getLogger(__name__)


class EmailService:
    """Service xử lý gửi email cho các tác vụ liên quan đến tài khoản."""

    @staticmethod
    def send_verification_email(user: User, token: str) -> None:
        """
        Gửi email xác thực tài khoản đến địa chỉ email của user.

        Args:
            user: User instance vừa đăng ký.
            token: Token xác thực dạng hex string.
        """
        verification_url = (
            f"{settings.FRONTEND_URL}/verify-email?token={token}"
        )

        subject = "Xác thực tài khoản Task Manager"
        message = (
            f"Xin chào {user.username},\n\n"
            f"Cảm ơn bạn đã đăng ký tài khoản Task Manager.\n"
            f"Vui lòng nhấp vào liên kết bên dưới để xác thực email của bạn:\n\n"
            f"{verification_url}\n\n"
            f"Liên kết này sẽ hết hạn sau 24 giờ.\n\n"
            f"Nếu bạn không thực hiện đăng ký, vui lòng bỏ qua email này.\n\n"
            f"Trân trọng,\nĐội ngũ Task Manager"
        )

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Verification email sent to user id={user.id}, email={user.email}")
        except Exception as exc:
            # Log lỗi nhưng không raise để không block quá trình đăng ký
            logger.error(
                f"Failed to send verification email to user id={user.id}: {exc}"
            )


class UserService:
    """Service xử lý logic nghiệp vụ liên quan đến User."""

    @staticmethod
    @transaction.atomic
    def register_user(data: dict) -> User:
        """
        Tạo tài khoản mới, sinh token xác thực và gửi email xác thực.

        Args:
            data: Dict chứa username, email, password (đã được validate bởi serializer).

        Returns:
            User: Instance user vừa được tạo.

        Raises:
            ValidationError: Nếu username hoặc email đã tồn tại (race condition).
        """
        try:
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"],
            )
            logger.info(f"New user registered: id={user.id}, username={user.username}")
        except Exception as exc:
            logger.error(f"Failed to create user '{data.get('username')}': {exc}")
            raise ValidationError("Không thể tạo tài khoản. Vui lòng thử lại.")

        # Sinh token và gửi email xác thực (ngoài atomic block để tránh rollback khi email lỗi)
        token = user.generate_verification_token()
        EmailService.send_verification_email(user, token)

        return user

    @staticmethod
    def login_user(username_or_email: str, password: str) -> User:
        """
        Xác thực người dùng bằng username hoặc email.

        Args:
            username_or_email: Username hoặc email của người dùng.
            password: Mật khẩu dạng plaintext.

        Returns:
            User: Instance user đã xác thực.

        Raises:
            AuthenticationFailed: Nếu thông tin đăng nhập không đúng.
        """
        # Thử xác thực bằng username trước
        user = authenticate(username=username_or_email, password=password)

        # Nếu không tìm thấy, thử tìm theo email rồi xác thực lại
        if user is None:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            logger.warning(
                f"Failed login attempt for identifier='{username_or_email}'"
            )
            raise AuthenticationFailed(
                "Thông tin đăng nhập không chính xác. Vui lòng kiểm tra lại."
            )

        if not user.is_email_verified:
            logger.warning(
                f"Login attempt with unverified email: id={user.id}, username={user.username}"
            )
            raise AuthenticationFailed(
                "Email chưa được xác thực. Vui lòng kiểm tra hộp thư và nhấp vào liên kết xác thực."
            )

        logger.info(f"User logged in: id={user.id}, username={user.username}")
        return user

    @staticmethod
    def verify_email(token: str) -> User:
        """
        Xác thực email của user bằng token.

        Args:
            token: Token xác thực từ URL.

        Returns:
            User: Instance user đã được xác thực email.

        Raises:
            ValidationError: Nếu token không hợp lệ hoặc đã được dùng.
        """
        if not token:
            raise ValidationError("Token xác thực không hợp lệ.")

        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            logger.warning(f"Invalid email verification token used: '{token[:8]}...'")
            raise ValidationError("Token xác thực không hợp lệ hoặc đã hết hạn.")

        if user.is_email_verified:
            raise ValidationError("Email này đã được xác thực trước đó.")

        user.is_email_verified = True
        user.email_verification_token = ""  # Vô hiệu hóa token sau khi dùng
        user.save(update_fields=["is_email_verified", "email_verification_token"])

        logger.info(f"Email verified for user id={user.id}, email={user.email}")
        return user

    @staticmethod
    def update_profile(user: User, data: dict) -> User:
        """
        Cập nhật thông tin profile của user.
        Chỉ cho phép cập nhật full_name và avatar_url.

        Args:
            user: User instance cần cập nhật.
            data: Dict chứa các trường được phép cập nhật.

        Returns:
            User: Instance user sau khi cập nhật.
        """
        allowed_fields = ["full_name", "avatar_url"]
        updated_fields = []

        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])
                updated_fields.append(field)

        if updated_fields:
            user.save(update_fields=updated_fields)
            logger.info(
                f"Profile updated for user id={user.id}, fields={updated_fields}"
            )

        return user
