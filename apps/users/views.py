import logging
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    UserProfileUpdateSerializer,
)
from .services import UserService

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """
    POST /api/auth/register/

    Đăng ký tài khoản mới. Sau khi đăng ký thành công, hệ thống sẽ
    gửi email xác thực đến địa chỉ email của người dùng.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Xử lý đăng ký tài khoản mới."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.register_user(serializer.validated_data)

        return Response(
            {
                "user": UserSerializer(user).data,
                "message": (
                    "Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/auth/login/

    Đăng nhập bằng username (hoặc email) và password.
    Trả về access token (60 phút) và refresh token (7 ngày).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Xử lý đăng nhập và phát hành JWT tokens."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.login_user(
            username_or_email=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class VerifyEmailView(APIView):
    """
    GET /api/auth/verify-email/?token=<token>

    Xác thực email của người dùng bằng token nhận được qua email.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        """Xử lý xác thực email từ token trong query param."""
        token = request.query_params.get("token", "")
        user = UserService.verify_email(token)

        return Response(
            {
                "message": "Xác thực email thành công! Bạn có thể đăng nhập ngay bây giờ.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class UserProfileView(APIView):
    """
    GET  /api/users/me/   — Lấy thông tin profile của user hiện tại.
    PATCH /api/users/me/  — Cập nhật full_name và/hoặc avatar_url.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Trả về thông tin profile của user đang đăng nhập."""
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Cập nhật profile. Chỉ cho phép thay đổi full_name và avatar_url."""
        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.update_profile(request.user, serializer.validated_data)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AvatarUploadView(APIView):
    """
    POST /api/users/me/avatar/

    Upload ảnh đại diện cho user hiện tại.
    Nhận file ảnh qua multipart/form-data (field name: 'avatar').
    Lưu file vào MEDIA_ROOT/avatars/ và cập nhật avatar_url của user.

    Giới hạn:
        - Chỉ chấp nhận file ảnh (image/*)
        - Kích thước tối đa: 2 MB
    """

    permission_classes = [IsAuthenticated]

    MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
    ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    UPLOAD_DIR = 'avatars'

    def post(self, request):
        """Xử lý upload ảnh đại diện."""
        avatar_file = request.FILES.get('avatar')

        if not avatar_file:
            return Response(
                {'avatar': ['Vui lòng chọn file ảnh.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate content type
        if avatar_file.content_type not in self.ALLOWED_CONTENT_TYPES:
            return Response(
                {'avatar': ['Chỉ chấp nhận file ảnh (JPEG, PNG, GIF, WebP).']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size
        if avatar_file.size > self.MAX_SIZE_BYTES:
            return Response(
                {'avatar': ['Ảnh không được vượt quá 2 MB.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build a safe filename: <user_id>.<ext>
        ext = os.path.splitext(avatar_file.name)[1].lower() or '.jpg'
        filename = f'{request.user.id}{ext}'

        # Save file using Django's default storage
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        from django.conf import settings

        save_path = os.path.join(self.UPLOAD_DIR, filename)

        # Delete old file if it exists to avoid accumulation
        if default_storage.exists(save_path):
            default_storage.delete(save_path)

        saved_path = default_storage.save(save_path, ContentFile(avatar_file.read()))

        # Build the absolute URL for the saved file
        avatar_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)

        # Update user's avatar_url
        user = UserService.update_profile(request.user, {'avatar_url': avatar_url})

        logger.info(
            f"AvatarUploadView.post: user_id={request.user.id}, "
            f"file={filename}, url={avatar_url}"
        )

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
