from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer trả về thông tin public của User. Không bao gồm password."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "avatar_url",
            "is_email_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """
    Serializer cho API đăng ký tài khoản.
    Validate username, email unique và password khớp confirm_password.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value: str) -> str:
        """Kiểm tra username chưa được sử dụng."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.")
        return value

    def validate_email(self, value: str) -> str:
        """Kiểm tra email chưa được đăng ký."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email đã được sử dụng. Vui lòng dùng email khác.")
        return value

    def validate(self, data: dict) -> dict:
        """Kiểm tra password và confirm_password khớp nhau."""
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Mật khẩu xác nhận không khớp."})
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer cho API đăng nhập. Hỗ trợ đăng nhập bằng username hoặc email."""

    username = serializers.CharField(
        help_text="Có thể nhập username hoặc email."
    )
    password = serializers.CharField(write_only=True)


class UserProfileUpdateSerializer(serializers.Serializer):
    """
    Serializer cho API cập nhật profile.
    Chỉ cho phép cập nhật full_name và avatar_url.
    """

    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True)
