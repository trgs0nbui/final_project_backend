import uuid
import secrets

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model sử dụng UUID làm primary key.
    Hỗ trợ xác thực bằng username hoặc email.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)

    full_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)

    # Email verification
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username

    def generate_verification_token(self) -> str:
        """
        Tạo token ngẫu nhiên 32 bytes (64 ký tự hex) dùng để xác thực email.

        Returns:
            str: Token dạng hex string.
        """
        token = secrets.token_hex(32)
        self.email_verification_token = token
        self.save(update_fields=["email_verification_token"])
        return token
