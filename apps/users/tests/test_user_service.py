"""
Unit tests cho UserService sử dụng pytest-django.
Validates: Requirements 14.1, 14.7
"""
from unittest.mock import patch

import pytest
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.users.models import User
from apps.users.services import UserService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_data():
    """Dữ liệu hợp lệ để đăng ký user."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "StrongPass123",
    }


@pytest.fixture
def registered_user(db, valid_data):
    """User đã được đăng ký, email service bị mock."""
    with patch("apps.users.services.EmailService.send_verification_email"):
        return UserService.register_user(valid_data)


# ===========================================================================
# register_user
# ===========================================================================

@pytest.mark.django_db
class TestRegisterUser:
    """Tests cho UserService.register_user — Requirements 14.1, 14.7"""

    def test_register_success_returns_user_instance(self, db, valid_data):
        """Đăng ký với dữ liệu hợp lệ trả về User instance."""
        with patch("apps.users.services.EmailService.send_verification_email"):
            user = UserService.register_user(valid_data)

        assert isinstance(user, User)

    def test_register_success_persists_to_database(self, db, valid_data):
        """User được lưu vào database sau khi đăng ký."""
        with patch("apps.users.services.EmailService.send_verification_email"):
            UserService.register_user(valid_data)

        assert User.objects.filter(username=valid_data["username"]).exists()

    def test_register_success_username_and_email_match(self, db, valid_data):
        """Username và email của user trả về khớp với dữ liệu đầu vào."""
        with patch("apps.users.services.EmailService.send_verification_email") as mock_email:
            user = UserService.register_user(valid_data)

        assert user.username == valid_data["username"]
        assert user.email == valid_data["email"]
        mock_email.assert_called_once()

    def test_register_duplicate_email_raises_validation_error(self, registered_user, valid_data):
        """Đăng ký với email đã tồn tại phải raise ValidationError."""
        duplicate = {**valid_data, "username": "otheruser"}
        with patch("apps.users.services.EmailService.send_verification_email"):
            with pytest.raises(ValidationError):
                UserService.register_user(duplicate)

    def test_register_duplicate_username_raises_validation_error(self, registered_user, valid_data):
        """Đăng ký với username đã tồn tại phải raise ValidationError."""
        duplicate = {**valid_data, "email": "other@example.com"}
        with patch("apps.users.services.EmailService.send_verification_email"):
            with pytest.raises(ValidationError):
                UserService.register_user(duplicate)


# ===========================================================================
# login_user
# ===========================================================================

@pytest.mark.django_db
class TestLoginUser:
    """Tests cho UserService.login_user — Requirements 14.1, 14.7"""

    def test_login_with_username_returns_user(self, registered_user, valid_data):
        """Đăng nhập bằng username và password đúng trả về User instance."""
        user = UserService.login_user(valid_data["username"], valid_data["password"])

        assert isinstance(user, User)
        assert user.username == valid_data["username"]

    def test_login_with_email_returns_user(self, registered_user, valid_data):
        """Đăng nhập bằng email và password đúng trả về User instance."""
        user = UserService.login_user(valid_data["email"], valid_data["password"])

        assert isinstance(user, User)
        assert user.email == valid_data["email"]

    def test_login_wrong_password_raises_authentication_failed(self, registered_user, valid_data):
        """Đăng nhập với password sai phải raise AuthenticationFailed."""
        with pytest.raises(AuthenticationFailed):
            UserService.login_user(valid_data["username"], "WrongPassword!")

    def test_login_nonexistent_user_raises_authentication_failed(self, db):
        """Đăng nhập với username không tồn tại phải raise AuthenticationFailed."""
        with pytest.raises(AuthenticationFailed):
            UserService.login_user("nonexistent_user", "SomePassword123")


# ===========================================================================
# Password hashing
# ===========================================================================

@pytest.mark.django_db
class TestPasswordHashing:
    """Tests đảm bảo password được băm đúng cách — Requirements 14.1"""

    def test_password_is_not_stored_as_plaintext(self, registered_user, valid_data):
        """Password lưu trong DB không phải plaintext."""
        registered_user.refresh_from_db()
        assert registered_user.password != valid_data["password"]

    def test_check_password_returns_true_for_correct_plaintext(self, registered_user, valid_data):
        """check_password() với plaintext đúng phải trả về True."""
        registered_user.refresh_from_db()
        assert registered_user.check_password(valid_data["password"])

    def test_check_password_returns_false_for_wrong_plaintext(self, registered_user):
        """check_password() với plaintext sai phải trả về False."""
        registered_user.refresh_from_db()
        assert not registered_user.check_password("WrongPassword!")


# ===========================================================================
# EmailService.send_verification_email
# ===========================================================================

@pytest.mark.django_db
class TestEmailService:
    """Tests cho EmailService.send_verification_email"""

    def test_send_verification_email_calls_send_mail(self, db, valid_data):
        """send_verification_email phải gọi send_mail với đúng tham số."""
        with patch("apps.users.services.EmailService.send_verification_email"):
            user = UserService.register_user(valid_data)

        with patch("apps.users.services.send_mail") as mock_send:
            from apps.users.services import EmailService
            EmailService.send_verification_email(user, "testtoken123")
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args
            assert user.email in call_kwargs[1]["recipient_list"]

    def test_send_verification_email_does_not_raise_on_smtp_error(self, db, valid_data):
        """Khi send_mail raise exception, EmailService không re-raise (không block đăng ký)."""
        with patch("apps.users.services.EmailService.send_verification_email"):
            user = UserService.register_user(valid_data)

        with patch("apps.users.services.send_mail", side_effect=Exception("SMTP error")):
            from apps.users.services import EmailService
            # Không raise — lỗi email không block quá trình đăng ký
            EmailService.send_verification_email(user, "testtoken123")


# ===========================================================================
# verify_email
# ===========================================================================

@pytest.mark.django_db
class TestVerifyEmail:
    """Tests cho UserService.verify_email"""

    def test_verify_email_with_valid_token_returns_user(self, registered_user):
        """Token hợp lệ phải trả về User instance."""
        token = registered_user.email_verification_token
        user = UserService.verify_email(token)
        assert isinstance(user, User)

    def test_verify_email_sets_is_email_verified_true(self, registered_user):
        """Sau khi verify, is_email_verified phải là True."""
        token = registered_user.email_verification_token
        UserService.verify_email(token)
        registered_user.refresh_from_db()
        assert registered_user.is_email_verified is True

    def test_verify_email_clears_token_after_use(self, registered_user):
        """Sau khi verify, email_verification_token phải bị xóa (empty string)."""
        token = registered_user.email_verification_token
        UserService.verify_email(token)
        registered_user.refresh_from_db()
        assert registered_user.email_verification_token == ""

    def test_verify_email_with_empty_token_raises_validation_error(self, db):
        """Token rỗng phải raise ValidationError."""
        with pytest.raises(ValidationError):
            UserService.verify_email("")

    def test_verify_email_with_invalid_token_raises_validation_error(self, db):
        """Token không tồn tại phải raise ValidationError."""
        with pytest.raises(ValidationError):
            UserService.verify_email("nonexistent_token_xyz")

    def test_verify_email_already_verified_raises_validation_error(self, registered_user):
        """Xác thực lại email đã verified phải raise ValidationError."""
        token = registered_user.email_verification_token
        UserService.verify_email(token)
        # Lấy token mới (đã bị xóa) — dùng token cũ sẽ raise vì không tìm thấy
        with pytest.raises(ValidationError):
            UserService.verify_email(token)

    def test_verify_email_already_verified_flag_raises_validation_error(self, registered_user):
        """User đã verified nhưng token vẫn còn — phải raise ValidationError."""
        # Đặt is_email_verified=True nhưng giữ token
        token = registered_user.email_verification_token
        registered_user.is_email_verified = True
        registered_user.save(update_fields=["is_email_verified"])

        with pytest.raises(ValidationError):
            UserService.verify_email(token)


# ===========================================================================
# update_profile
# ===========================================================================

@pytest.mark.django_db
class TestUpdateProfile:
    """Tests cho UserService.update_profile"""

    def test_update_full_name(self, registered_user):
        """Cập nhật full_name phải được lưu vào database."""
        UserService.update_profile(registered_user, {"full_name": "Nguyen Van A"})
        registered_user.refresh_from_db()
        assert registered_user.full_name == "Nguyen Van A"

    def test_update_avatar_url(self, registered_user):
        """Cập nhật avatar_url phải được lưu vào database."""
        UserService.update_profile(registered_user, {"avatar_url": "https://example.com/avatar.png"})
        registered_user.refresh_from_db()
        assert registered_user.avatar_url == "https://example.com/avatar.png"

    def test_update_both_fields(self, registered_user):
        """Cập nhật cả full_name và avatar_url cùng lúc."""
        UserService.update_profile(
            registered_user,
            {"full_name": "Tran Thi B", "avatar_url": "https://example.com/b.png"},
        )
        registered_user.refresh_from_db()
        assert registered_user.full_name == "Tran Thi B"
        assert registered_user.avatar_url == "https://example.com/b.png"

    def test_update_profile_returns_user_instance(self, registered_user):
        """update_profile phải trả về User instance."""
        result = UserService.update_profile(registered_user, {"full_name": "Test Name"})
        assert isinstance(result, User)

    def test_update_profile_ignores_disallowed_fields(self, registered_user):
        """Các trường không được phép (username, email) phải bị bỏ qua."""
        original_username = registered_user.username
        original_email = registered_user.email
        UserService.update_profile(
            registered_user,
            {"username": "hacked", "email": "hacked@evil.com", "full_name": "Allowed"},
        )
        registered_user.refresh_from_db()
        assert registered_user.username == original_username
        assert registered_user.email == original_email
        assert registered_user.full_name == "Allowed"

    def test_update_profile_with_empty_data_does_not_change_anything(self, registered_user):
        """Truyền dict rỗng không thay đổi gì."""
        original_full_name = registered_user.full_name
        UserService.update_profile(registered_user, {})
        registered_user.refresh_from_db()
        assert registered_user.full_name == original_full_name
