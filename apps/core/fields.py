from rest_framework import serializers
from django.core.exceptions import ValidationError
from apps.accounts.phone_numbers import normalize_iranian_mobile_number


class IranianPhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            normalized = normalize_iranian_mobile_number(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if normalized is None:
            raise serializers.ValidationError("Phone number is required.")
        return normalized
