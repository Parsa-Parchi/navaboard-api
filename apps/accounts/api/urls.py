from django.urls import path

from apps.accounts.api.views import OTPRequestAPIView


app_name = "accounts-api"

urlpatterns = [
    path(
        "auth/otp/request/",
        OTPRequestAPIView.as_view(),
        name="otp-request",
    ),
]