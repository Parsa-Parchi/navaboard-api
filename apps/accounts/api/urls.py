from django.urls import path

from apps.accounts.api.views import (
    CSRFTokenAPIView,
    PhoneChangeConfirmAPIView,
    PhoneChangeRequestAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    EmailVerificationConfirmAPIView,
    EmailVerificationRequestAPIView,
    ChangePasswordAPIView,
    CurrentUserProfileAPIView,
    EmailPasswordLoginAPIView,
    LogoutAPIView,
    OTPRequestAPIView,
    OTPVerificationAPIView,
    SetInitialPasswordAPIView,
    TokenRefreshAPIView,
    EmailSignupRequestAPIView,
    EmailSignupConfirmAPIView,
)
app_name = "accounts-api"

urlpatterns = [
    path("auth/csrf/", CSRFTokenAPIView.as_view(), name="csrf"),
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
    "auth/phone/change/request/",
    PhoneChangeRequestAPIView.as_view(),
    name="phone-change-request",
    ),

    path(
    "auth/phone/change/confirm/",
    PhoneChangeConfirmAPIView.as_view(),
    name="phone-change-confirm",
    ),

    path(
    "auth/email/signup/request/",
    EmailSignupRequestAPIView.as_view(),
    name="email-signup-request",
    ),

    path(
    "auth/email/signup/confirm/",
    EmailSignupConfirmAPIView.as_view(),
    name="email-signup-confirm",
    ),

    path(
        "auth/email/login/",
        EmailPasswordLoginAPIView.as_view(),
        name="email-login",
    ),

    path(
    "auth/email/verification/request/",
    EmailVerificationRequestAPIView.as_view(),
    name="email-verification-request",
    ),

    path(
    "auth/email/verification/confirm/",
    EmailVerificationConfirmAPIView.as_view(),
    name="email-verification-confirm",
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
    path(
    "auth/password/reset/request/",
    PasswordResetRequestAPIView.as_view(),
    name="password-reset-request",
    ),

    path(
    "auth/password/reset/confirm/",
    PasswordResetConfirmAPIView.as_view(),
    name="password-reset-confirm",
    ),


]