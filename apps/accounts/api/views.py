from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    OTPRequestResponseSerializer,
    OTPRequestSerializer,
)
from apps.accounts.services.otp import create_otp_challenge
from django.conf import settings
from drf_spectacular.utils import extend_schema

class OTPRequestAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPRequestSerializer

    @extend_schema(
        request=OTPRequestSerializer,
        responses={
            status.HTTP_201_CREATED: OTPRequestResponseSerializer,
        },
        tags=["auth"],
    )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = create_otp_challenge(
            phone_number=serializer.validated_data["phone_number"],
            purpose=serializer.validated_data["purpose"],
            requested_ip=self._get_client_ip(request),
        )

        response_data = {
            "detail": "OTP code has been generated.",
            "expires_at": result.challenge.expires_at,
        }

        if settings.OTP_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_otp_code"] = result.plain_code


        return Response(response_data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _get_client_ip(request) -> str | None:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip()

        return request.META.get("REMOTE_ADDR")