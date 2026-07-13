from django.urls import path

from apps.accounts.api.views import (
    ChangePasswordAPIView,
    CurrentUserProfileAPIView,
    EmailPasswordLoginAPIView,
    LogoutAPIView,
    OTPRequestAPIView,
    OTPVerificationAPIView,
    SetInitialPasswordAPIView,
    TokenRefreshAPIView,
)
app_name = "accounts-api"

urlpatterns = [
    path(
        "auth/otp/request/",
        OTPRequestAPIView.as_view(),
        name="otp-request",
    ),

    path(
        "auth/otp/verify/",
        OTPVerificationAPIView.as_view(),
        name="otp-verify",
    ),

    path(
        "auth/token/refresh/",
        TokenRefreshAPIView.as_view(),
        name="token-refresh",
    ),
    path(
        "auth/logout/",
        LogoutAPIView.as_view(),
        name="logout",
    ),
    path(
        "auth/me/",
        CurrentUserProfileAPIView.as_view(),
        name="me",
    ),

    path(
        "auth/email/login/",
        EmailPasswordLoginAPIView.as_view(),
        name="email-login",
    ),
    path(
        "auth/password/set/",
        SetInitialPasswordAPIView.as_view(),
        name="set-password",
    ),

    path(
        "auth/password/change/",
        ChangePasswordAPIView.as_view(),
        name="change-password",
    ),
]