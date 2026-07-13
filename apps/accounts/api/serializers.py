from rest_framework import serializers

from apps.accounts.models import OTPChallenge
from apps.accounts.phone_numbers import normalize_iranian_mobile_number
from django.contrib.auth import get_user_model

User = get_user_model()

class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=32,
        write_only=True,
    )
    purpose = serializers.ChoiceField(
        choices=OTPChallenge.Purpose.choices,
        default=OTPChallenge.Purpose.LOGIN,
        write_only=True,
    )

    def validate_phone_number(self, value: str) -> str:
        normalized_phone_number = normalize_iranian_mobile_number(value)

        if normalized_phone_number is None:
            raise serializers.ValidationError("Phone number is required.")

        return normalized_phone_number


class OTPRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    expires_at = serializers.DateTimeField()
    development_otp_code = serializers.CharField(
        required=False,
    )

class OTPVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=32,
        write_only=True,
    )
    code = serializers.CharField(
        max_length=6,
        write_only=True,
    )
    purpose = serializers.ChoiceField(
        choices=OTPChallenge.Purpose.choices,
        default=OTPChallenge.Purpose.LOGIN,
        write_only=True,
    )

    def validate_phone_number(self, value: str) -> str:
        normalized_phone_number = normalize_iranian_mobile_number(value)

        if normalized_phone_number is None:
            raise serializers.ValidationError("Phone number is required.")

        return normalized_phone_number

    def validate_code(self, value: str) -> str:
        normalized_code = value.strip()

        if len(normalized_code) != 6 or not normalized_code.isdigit():
            raise serializers.ValidationError("OTP code must be a 6-digit number.")

        return normalized_code


class AuthenticatedUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone_number = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)
    full_name = serializers.CharField()
    is_phone_verified = serializers.BooleanField()


class OTPVerificationResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    token_type = serializers.CharField()
    user_created = serializers.BooleanField()
    user = AuthenticatedUserSerializer()

class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
    )


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    token_type = serializers.CharField()


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
    )


class LogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()

class CurrentUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "email",
            "full_name",
            "is_phone_verified",
            "is_email_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "phone_number",
            "email",
            "is_phone_verified",
            "is_email_verified",
            "created_at",
            "updated_at",
        )

    def validate_full_name(self, value: str) -> str:
        return value.strip()

class EmailPasswordLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        write_only=True,
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

class SetInitialPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )
    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

class EmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        write_only=True,
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class EmailVerificationRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    expires_at = serializers.DateTimeField()
    development_verification_code = serializers.CharField(
        required=False,
    )


class EmailVerificationConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(
        write_only=True,
    )
    code = serializers.CharField(
        max_length=6,
        write_only=True,
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_code(self, value: str) -> str:
        normalized_code = value.strip()

        if len(normalized_code) != 6 or not normalized_code.isdigit():
            raise serializers.ValidationError(
                "Verification code must be a 6-digit number."
            )

        return normalized_code


class EmailVerificationConfirmResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    email = serializers.EmailField()
    is_email_verified = serializers.BooleanField()