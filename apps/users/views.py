import logging

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
