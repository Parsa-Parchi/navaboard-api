from __future__ import annotations

from hashlib import sha256

from django.core.exceptions import ValidationError
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from apps.accounts.phone_numbers import normalize_iranian_mobile_number


def get_client_ip(request) -> str | None:
    return BaseThrottle().get_ident(request)


class _ClientIPRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view) -> str | None:
        client_ip = self.get_ident(request)

        if not client_ip:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": client_ip,
        }


class _PhoneNumberRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view) -> str | None:
        request_data = request.data

        if not hasattr(request_data, "get"):
            return None

        try:
            phone_number = normalize_iranian_mobile_number(
                request_data.get("phone_number")
            )
        except (TypeError, ValidationError):
            return None

        if phone_number is None:
            return None

        phone_digest = sha256(phone_number.encode("utf-8")).hexdigest()

        return self.cache_format % {
            "scope": self.scope,
            "ident": phone_digest,
        }


class OTPRequestIPThrottle(_ClientIPRateThrottle):
    scope = "otp_request_ip"


class OTPRequestPhoneThrottle(_PhoneNumberRateThrottle):
    scope = "otp_request_phone"


class OTPVerificationIPThrottle(_ClientIPRateThrottle):
    scope = "otp_verify_ip"


class OTPVerificationPhoneThrottle(_PhoneNumberRateThrottle):
    scope = "otp_verify_phone"
