from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.phone_numbers import normalize_iranian_mobile_number


OTP_CODE_LENGTH = 6
OTP_LIFETIME = timedelta(minutes=2)


@dataclass(frozen=True)
class OTPChallengeRequestResult:
    challenge: OTPChallenge
    plain_code: str


def generate_numeric_otp_code(length: int = OTP_CODE_LENGTH) -> str:
    if length < 4:
        raise ValueError("OTP code length must be at least 4 digits.")

    max_value = 10**length
    return str(secrets.randbelow(max_value)).zfill(length)


def hash_otp_code(plain_code: str) -> str:
    return make_password(plain_code)


def check_otp_code(plain_code: str, encoded_code: str) -> bool:
    return check_password(plain_code, encoded_code)


def create_otp_challenge(
    *,
    phone_number: str,
    purpose: str = OTPChallenge.Purpose.LOGIN,
    requested_ip: str | None = None,
) -> OTPChallengeRequestResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)

    if normalized_phone_number is None:
        raise ValidationError("Phone number is required.")

    now = timezone.now()

    OTPChallenge.objects.filter(
        phone_number=normalized_phone_number,
        purpose=purpose,
        used_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    plain_code = generate_numeric_otp_code()
    challenge = OTPChallenge.objects.create(
        phone_number=normalized_phone_number,
        purpose=purpose,
        code_hash=hash_otp_code(plain_code),
        expires_at=now + OTP_LIFETIME,
        requested_ip=requested_ip,
    )

    return OTPChallengeRequestResult(
        challenge=challenge,
        plain_code=plain_code,
    )