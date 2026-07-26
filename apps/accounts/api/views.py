from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.services.email_auth import authenticate_with_email_and_password
from apps.accounts.services.password_reset import (
    confirm_password_reset,
    create_password_reset_challenge,
)
from apps.accounts.services.email_verification import (
    create_email_verification_challenge,
    verify_email_challenge,
)

from apps.accounts.services.email_signup import (
    confirm_email_signup,
    create_email_signup_challenge,
)


from apps.accounts.services.passwords import (
    change_password_for_user,
    set_initial_password_for_user,
)

from apps.accounts.services.phone_change import (
    confirm_phone_change,
    create_phone_change_challenge,
)

from apps.accounts.api.serializers import (
    PhoneChangeConfirmResponseSerializer,
    PhoneChangeConfirmSerializer,
    PhoneChangeRequestResponseSerializer,
    PhoneChangeRequestSerializer,
    PasswordResetConfirmResponseSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestResponseSerializer,
    PasswordResetRequestSerializer,
    EmailVerificationConfirmResponseSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestResponseSerializer,
    EmailVerificationRequestSerializer,
    ChangePasswordSerializer,
    CurrentUserProfileSerializer,
    EmailPasswordLoginSerializer,
    LogoutResponseSerializer,
    OTPRequestResponseSerializer,
    OTPRequestSerializer,
    OTPVerificationResponseSerializer,
    OTPVerificationSerializer,
    SetInitialPasswordSerializer,
    ThrottledResponseSerializer,
    TokenRefreshResponseSerializer,
    EmailSignupConfirmRequestSerializer,
    EmailSignupConfirmResponseSerializer,
    EmailSignupRequestResponseSerializer,
    EmailSignupRequestSerializer,
)

from apps.accounts.api.cookies import (
    clear_refresh_token_cookie,
    get_refresh_token_from_cookie,
    set_refresh_token_cookie,
)
from apps.accounts.api.throttles import (
    OTPRequestIPThrottle,
    OTPRequestPhoneThrottle,
    OTPVerificationIPThrottle,
    OTPVerificationPhoneThrottle,
    get_client_ip,
)


from apps.accounts.services.otp import (
    create_login_otp_challenge,
    verify_login_otp_challenge,
)
from apps.accounts.services.tokens import (
    blacklist_refresh_token,
    issue_auth_token_pair,
    refresh_auth_token_pair,
)

from apps.accounts.services.notifications import (
    NotificationDeliveryError,
    send_email_verification_code,
    send_login_otp_code,
    send_password_reset_code,
    send_phone_change_code,
)

from django.conf import settings
from drf_spectacular.utils import extend_schema

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException, ValidationError as DRFValidationError



class NotificationDeliveryAPIException(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Verification code could not be delivered."
    default_code = "notification_delivery_failed"


class OTPRequestAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPRequestSerializer
    throttle_classes = [OTPRequestIPThrottle, OTPRequestPhoneThrottle]

    @extend_schema(
        request=OTPRequestSerializer,
        responses={
            status.HTTP_201_CREATED: OTPRequestResponseSerializer,
            status.HTTP_429_TOO_MANY_REQUESTS: ThrottledResponseSerializer,
        },
        tags=["auth"],
    )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = create_login_otp_challenge(
            phone_number=serializer.validated_data["phone_number"],
            requested_ip=get_client_ip(request),
        )

        try:
            send_login_otp_code(
                phone_number=result.challenge.phone_number,
                code=result.plain_code,
            )
        except NotificationDeliveryError as exc:
            raise NotificationDeliveryAPIException() from exc


        response_data = {
            "detail": "OTP code has been generated.",
            "expires_at": result.challenge.expires_at,
        }

        if settings.OTP_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_otp_code"] = result.plain_code


        return Response(response_data, status=status.HTTP_201_CREATED)


class OTPVerificationAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPVerificationSerializer
    throttle_classes = [OTPVerificationIPThrottle, OTPVerificationPhoneThrottle]

    @extend_schema(
        request=OTPVerificationSerializer,
        responses={
            status.HTTP_200_OK: OTPVerificationResponseSerializer,
            status.HTTP_429_TOO_MANY_REQUESTS: ThrottledResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verification_result = verify_login_otp_challenge(
                phone_number=serializer.validated_data["phone_number"],
                plain_code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        token_pair = issue_auth_token_pair(verification_result.user)

        response_data = {
            "access": token_pair.access,
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

        response = Response(response_data, status=status.HTTP_200_OK)
        set_refresh_token_cookie(response, token_pair.refresh)

        return response

class TokenRefreshAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: TokenRefreshResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        refresh_token = get_refresh_token_from_cookie(request)

        try:
            token_pair = refresh_auth_token_pair(refresh_token or "")
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        response_data = {
            "access": token_pair.access,
            "token_type": "Bearer",
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        set_refresh_token_cookie(response, token_pair.refresh)

        return response

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        refresh_token = get_refresh_token_from_cookie(request)

        response = Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )

        if refresh_token:
            try:
                blacklist_refresh_token(refresh_token)
            except DjangoValidationError:
                pass

        clear_refresh_token_cookie(response)

        return response

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

    @extend_schema(
        request=CurrentUserProfileSerializer,
        responses={
            status.HTTP_200_OK: CurrentUserProfileSerializer,
        },
        tags=["auth"],
    )
    def put(self, request):
        serializer = self.serializer_class(
            instance=request.user,
            data=request.data,
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

        response = Response(response_data, status=status.HTTP_200_OK)
        set_refresh_token_cookie(response, token_pair.refresh)

        return response


class EmailSignupRequestAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailSignupRequestSerializer

    @extend_schema(
        request=EmailSignupRequestSerializer,
        responses={
            status.HTTP_201_CREATED: EmailSignupRequestResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = create_email_signup_challenge(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                full_name=serializer.validated_data.get("full_name", ""),
                requested_ip=self._get_client_ip(request),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        try:
            send_email_verification_code(
                email=result.challenge.email,
                code=result.plain_code,
            )
        except NotificationDeliveryError as exc:
            raise NotificationDeliveryAPIException() from exc

        response_data = {
            "detail": "Email signup verification code has been generated.",
            "user_created": result.user_created,
        }

        if settings.EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_email_verification_code"] = result.plain_code

        return Response(response_data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _get_client_ip(request) -> str | None:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip()

        return request.META.get("REMOTE_ADDR")


class EmailSignupConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailSignupConfirmRequestSerializer

    @extend_schema(
        request=EmailSignupConfirmRequestSerializer,
        responses={
            status.HTTP_200_OK: EmailSignupConfirmResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = confirm_email_signup(
                email=serializer.validated_data["email"],
                plain_code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        token_pair = issue_auth_token_pair(result.user)

        response_data = {
            "access": token_pair.access,
            "token_type": "Bearer",
            "user": {
                "id": result.user.id,
                "phone_number": result.user.phone_number,
                "email": result.user.email,
                "full_name": result.user.full_name,
                "is_phone_verified": result.user.is_phone_verified,
            },
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        set_refresh_token_cookie(response, token_pair.refresh)

        return response

class SetInitialPasswordAPIView(APIView):
    serializer_class = SetInitialPasswordSerializer

    @extend_schema(
        request=SetInitialPasswordSerializer,
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            set_initial_password_for_user(
                user=request.user,
                password=serializer.validated_data["password"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        response = Response(
            {
                "detail": (
                    "Password has been set successfully. "
                    "Please sign in again."
                )
            },
            status=status.HTTP_200_OK,
        )
        clear_refresh_token_cookie(response)

        return response

class ChangePasswordAPIView(APIView):
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            change_password_for_user(
                user=request.user,
                current_password=serializer.validated_data["current_password"],
                new_password=serializer.validated_data["new_password"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        response = Response(
            {
                "detail": (
                    "Password has been changed successfully. "
                    "Please sign in again."
                )
            },
            status=status.HTTP_200_OK,
        )
        clear_refresh_token_cookie(response)

        return response

class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        request=PasswordResetRequestSerializer,
        responses={status.HTTP_201_CREATED: PasswordResetRequestResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = create_password_reset_challenge(
                phone_number=serializer.validated_data["phone_number"],
                requested_ip=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        try:
            send_password_reset_code(
                phone_number=result.challenge.phone_number,
                code=result.plain_code,
            )
        except NotificationDeliveryError as exc:
            raise NotificationDeliveryAPIException() from exc

        response_data = {
            "detail": "Password reset code has been created.",
            "expires_at": result.challenge.expires_at,
        }

        if settings.OTP_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_otp_code"] = result.plain_code

        return Response(response_data, status=status.HTTP_201_CREATED)


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        request=PasswordResetConfirmSerializer,
        responses={status.HTTP_200_OK: PasswordResetConfirmResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            confirm_password_reset(
                phone_number=serializer.validated_data["phone_number"],
                plain_code=serializer.validated_data["code"],
                new_password=serializer.validated_data["new_password"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        response = Response(
            {
                "detail": (
                    "Password has been reset successfully. "
                    "Please sign in again."
                ),
            },
            status=status.HTTP_200_OK,
        )
        clear_refresh_token_cookie(response)

        return response

class EmailVerificationRequestAPIView(APIView):
    @extend_schema(
        tags=["auth"],
        request=EmailVerificationRequestSerializer,
        responses={status.HTTP_201_CREATED: EmailVerificationRequestResponseSerializer},
    )
    def post(self, request):
        serializer = EmailVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = create_email_verification_challenge(
                user=request.user,
                email=serializer.validated_data["email"],
                requested_ip=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        try:
            send_email_verification_code(
                email=result.challenge.email,
                code=result.plain_code,
            )
        except NotificationDeliveryError as exc:
            raise NotificationDeliveryAPIException() from exc

        response_data = {
            "detail": "Email verification code has been created.",
            "expires_at": result.challenge.expires_at,
        }

        if settings.EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_verification_code"] = result.plain_code

        return Response(response_data, status=status.HTTP_201_CREATED)


class EmailVerificationConfirmAPIView(APIView):
    @extend_schema(
        tags=["auth"],
        request=EmailVerificationConfirmSerializer,
        responses={status.HTTP_200_OK: EmailVerificationConfirmResponseSerializer},
    )
    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = verify_email_challenge(
                user=request.user,
                email=serializer.validated_data["email"],
                plain_code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(
            {
                "detail": "Email address has been verified successfully.",
                "email": result.user.email,
                "is_email_verified": result.user.is_email_verified,
            },
            status=status.HTTP_200_OK,
        )

class PhoneChangeRequestAPIView(APIView):
    @extend_schema(
        tags=["auth"],
        request=PhoneChangeRequestSerializer,
        responses={status.HTTP_201_CREATED: PhoneChangeRequestResponseSerializer},
    )
    def post(self, request):
        serializer = PhoneChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = create_phone_change_challenge(
                user=request.user,
                phone_number=serializer.validated_data["phone_number"],
                requested_ip=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        try:
            send_phone_change_code(
                phone_number=result.challenge.phone_number,
                code=result.plain_code,
            )
        except NotificationDeliveryError as exc:
            raise NotificationDeliveryAPIException() from exc

        response_data = {
            "detail": "Phone change code has been created.",
            "expires_at": result.challenge.expires_at,
        }

        if settings.OTP_DEVELOPMENT_CODE_IN_RESPONSE:
            response_data["development_otp_code"] = result.plain_code

        return Response(response_data, status=status.HTTP_201_CREATED)


class PhoneChangeConfirmAPIView(APIView):
    @extend_schema(
        tags=["auth"],
        request=PhoneChangeConfirmSerializer,
        responses={status.HTTP_200_OK: PhoneChangeConfirmResponseSerializer},
    )
    def post(self, request):
        serializer = PhoneChangeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = confirm_phone_change(
                user=request.user,
                phone_number=serializer.validated_data["phone_number"],
                plain_code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        return Response(
            {
                "detail": "Phone number has been changed successfully.",
                "phone_number": result.user.phone_number,
                "is_phone_verified": result.user.is_phone_verified,
            },
            status=status.HTTP_200_OK,
        )
