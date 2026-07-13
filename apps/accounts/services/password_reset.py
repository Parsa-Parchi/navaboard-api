from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.phone_numbers import normalize_iranian_mobile_number
from apps.accounts.services.otp import (
    check_otp_code,
    create_otp_challenge,
)


@dataclass(frozen=True)
class PasswordResetRequestResult:
    challenge: OTPChallenge
    plain_code: str


@dataclass(frozen=True)
class PasswordResetConfirmResult:
    challenge: OTPChallenge
    user: Any


def _get_active_user_by_phone_number(phone_number: str) -> Any:
    User = get_user_model()

    try:
        user = User.objects.get(phone_number=phone_number)
    except User.DoesNotExist as exc:
        raise ValidationError("No active account found for this phone number.") from exc

    if not user.is_active:
        raise ValidationError("User account is inactive.")

    if not user.is_phone_verified:
        raise ValidationError("Phone number is not verified.")

    return user


def create_password_reset_challenge(
    *,
    phone_number: str,
    requested_ip: str | None = None,
) -> PasswordResetRequestResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)

    _get_active_user_by_phone_number(normalized_phone_number)

    result = create_otp_challenge(
        phone_number=normalized_phone_number,
        purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        requested_ip=requested_ip,
    )

    return PasswordResetRequestResult(
        challenge=result.challenge,
        plain_code=result.plain_code,
    )


def confirm_password_reset(
    *,
    phone_number: str,
    plain_code: str,
    new_password: str,
) -> PasswordResetConfirmResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)
    submitted_code = plain_code.strip()

    if not submitted_code:
        raise ValidationError("Password reset code is required.")

    if not new_password:
        raise ValidationError("New password is required.")

    invalid_code_submitted = False

    with transaction.atomic():
        user = _get_active_user_by_phone_number(normalized_phone_number)

        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(
                phone_number=normalized_phone_number,
                purpose=OTPChallenge.Purpose.PASSWORD_RESET,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if challenge is None:
            raise ValidationError("No active password reset challenge found.")

        if challenge.is_expired:
            raise ValidationError("Password reset code has expired.")

        if not challenge.has_attempts_remaining:
            raise ValidationError("Password reset challenge has no attempts remaining.")

        if not check_otp_code(submitted_code, challenge.code_hash):
            challenge.attempts_count += 1
            challenge.save(update_fields=["attempts_count"])
            invalid_code_submitted = True
        else:
            validate_password(new_password, user=user)

            user.set_password(new_password)
            user.save(update_fields=["password", "updated_at"])

            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])

    if invalid_code_submitted:
        raise ValidationError("Invalid password reset code.")

    return PasswordResetConfirmResult(
        challenge=challenge,
        user=user,
    )