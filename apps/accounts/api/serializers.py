from rest_framework import serializers

from apps.accounts.models import OTPChallenge
from apps.accounts.phone_numbers import normalize_iranian_mobile_number


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