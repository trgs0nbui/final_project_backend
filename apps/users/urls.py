from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, LoginView, VerifyEmailView, UserProfileView

urlpatterns = [
    # Authentication
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),

    # User profile
    path("users/me/", UserProfileView.as_view(), name="user-profile"),
]
