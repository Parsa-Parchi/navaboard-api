from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.phone_numbers import normalize_iranian_mobile_number

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction


OTP_CODE_LENGTH = 6
OTP_LIFETIME = timedelta(minutes=2)


@dataclass(frozen=True)
class OTPChallengeRequestResult:
    challenge: OTPChallenge
    plain_code: str

@dataclass(frozen=True)
class OTPVerificationResult:
    challenge: OTPChallenge
    user: Any
    user_created: bool


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

def verify_otp_challenge(
    *,
    phone_number: str,
    plain_code: str,
    purpose: str = OTPChallenge.Purpose.LOGIN,
) -> OTPVerificationResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)

    if normalized_phone_number is None:
        raise ValidationError("Phone number is required.")

    submitted_code = plain_code.strip()

    if not submitted_code:
        raise ValidationError("OTP code is required.")

    invalid_code_submitted = False
    user = None
    user_created = False

    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(
                phone_number=normalized_phone_number,
                purpose=purpose,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if challenge is None:
            raise ValidationError("No active OTP challenge found.")

        if challenge.is_expired:
            raise ValidationError("OTP code has expired.")

        if not challenge.has_attempts_remaining:
            raise ValidationError("OTP challenge has no attempts remaining.")

        if not check_otp_code(submitted_code, challenge.code_hash):
            challenge.attempts_count += 1
            challenge.save(update_fields=["attempts_count"])
            invalid_code_submitted = True
        else:
            User = get_user_model()

            try:
                user = User.objects.select_for_update().get(
                    phone_number=normalized_phone_number,
                )
                user_created = False
            except User.DoesNotExist:
                user = User.objects.create_user(
                    phone_number=normalized_phone_number,
                    is_phone_verified=True,
                )
                user_created = True
            else:
                if not user.is_phone_verified:
                    user.is_phone_verified = True
                    user.save(update_fields=["is_phone_verified", "updated_at"])

            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])

    if invalid_code_submitted:
        raise ValidationError("Invalid OTP code.")

    return OTPVerificationResult(
        challenge=challenge,
        user=user,
        user_created=user_created,
    )