from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.services.email_auth import authenticate_with_email_and_password
from apps.accounts.api.serializers import (
    CurrentUserProfileSerializer,
    EmailPasswordLoginSerializer,
    LogoutRequestSerializer,
    LogoutResponseSerializer,
    OTPRequestResponseSerializer,
    OTPRequestSerializer,
    OTPVerificationResponseSerializer,
    OTPVerificationSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
)
from apps.accounts.services.otp import create_otp_challenge, verify_otp_challenge
from apps.accounts.services.tokens import (
    blacklist_refresh_token,
    issue_auth_token_pair,
    refresh_auth_token_pair,
)

from django.conf import settings
from drf_spectacular.utils import extend_schema

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError



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


class OTPVerificationAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPVerificationSerializer

    @extend_schema(
        request=OTPVerificationSerializer,
        responses={
            status.HTTP_200_OK: OTPVerificationResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verification_result = verify_otp_challenge(
                phone_number=serializer.validated_data["phone_number"],
                plain_code=serializer.validated_data["code"],
                purpose=serializer.validated_data["purpose"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        token_pair = issue_auth_token_pair(verification_result.user)

        response_data = {
            "access": token_pair.access,
            "refresh": token_pair.refresh,
            "token_type": "Bearer",
            "user_created": verification_result.user_created,
            "user": {
                "id": verification_result.user.id,
                "phone_number": verification_result.user.phone_number,
                "email": verification_result.user.email,
                "full_name": verification_result.user.full_name,
                "is_phone_verified": verification_result.user.is_phone_verified,
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)

class TokenRefreshAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshRequestSerializer

    @extend_schema(
        request=TokenRefreshRequestSerializer,
        responses={
            status.HTTP_200_OK: TokenRefreshResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token_pair = refresh_auth_token_pair(
                serializer.validated_data["refresh"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        response_data = {
            "access": token_pair.access,
            "refresh": token_pair.refresh,
            "token_type": "Bearer",
        }

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LogoutRequestSerializer

    @extend_schema(
        request=LogoutRequestSerializer,
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            blacklist_refresh_token(serializer.validated_data["refresh"])
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )

class CurrentUserProfileAPIView(APIView):
    serializer_class = CurrentUserProfileSerializer

    @extend_schema(
        responses={
            status.HTTP_200_OK: CurrentUserProfileSerializer,
        },
        tags=["auth"],
    )
    def get(self, request):
        serializer = self.serializer_class(request.user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=CurrentUserProfileSerializer,
        responses={
            status.HTTP_200_OK: CurrentUserProfileSerializer,
        },
        tags=["auth"],
    )
    def patch(self, request):
        serializer = self.serializer_class(
            instance=request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

class EmailPasswordLoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailPasswordLoginSerializer

    @extend_schema(
        request=EmailPasswordLoginSerializer,
        responses={
            status.HTTP_200_OK: OTPVerificationResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = authenticate_with_email_and_password(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        token_pair = issue_auth_token_pair(user)

        response_data = {
            "access": token_pair.access,
            "refresh": token_pair.refresh,
            "token_type": "Bearer",
            "user_created": False,
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "email": user.email,
                "full_name": user.full_name,
                "is_phone_verified": user.is_phone_verified,
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)