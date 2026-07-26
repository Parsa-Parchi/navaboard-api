from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
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
class PhoneChangeRequestResult:
    challenge: OTPChallenge
    plain_code: str


@dataclass(frozen=True)
class PhoneChangeConfirmResult:
    challenge: OTPChallenge
    user: Any


def _validate_user_can_use_phone_number(
    *,
    user: Any,
    phone_number: str,
) -> None:
    user_model = get_user_model()

    if (
        user_model.objects.filter(phone_number=phone_number)
        .exclude(id=user.id)
        .exists()
    ):
        raise ValidationError("Phone number is already in use.")

    current_phone_number = (user.phone_number or "").strip()

    if current_phone_number == phone_number and user.is_phone_verified:
        raise ValidationError("Phone number is already verified.")


def create_phone_change_challenge(
    *,
    user: Any,
    phone_number: str,
    requested_ip: str | None = None,
) -> PhoneChangeRequestResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)

    if not user.is_active:
        raise ValidationError("User account is inactive.")

    _validate_user_can_use_phone_number(
        user=user,
        phone_number=normalized_phone_number,
    )

    result = create_otp_challenge(
        phone_number=normalized_phone_number,
        purpose=OTPChallenge.Purpose.CHANGE_PHONE,
        requested_ip=requested_ip,
        requested_by=user,
    )

    return PhoneChangeRequestResult(
        challenge=result.challenge,
        plain_code=result.plain_code,
    )


def confirm_phone_change(
    *,
    user: Any,
    phone_number: str,
    plain_code: str,
) -> PhoneChangeConfirmResult:
    normalized_phone_number = normalize_iranian_mobile_number(phone_number)
    submitted_code = plain_code.strip()

    if not submitted_code:
        raise ValidationError("Phone change code is required.")

    invalid_code_submitted = False

    with transaction.atomic():
        user_model = get_user_model()
        locked_user = user_model.objects.select_for_update().get(id=user.id)

        if not locked_user.is_active:
            raise ValidationError("User account is inactive.")

        _validate_user_can_use_phone_number(
            user=locked_user,
            phone_number=normalized_phone_number,
        )

        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(
                phone_number=normalized_phone_number,
                purpose=OTPChallenge.Purpose.CHANGE_PHONE,
                requested_by=locked_user,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if challenge is None:
            raise ValidationError("No active phone change challenge found.")

        if challenge.is_expired:
            raise ValidationError("Phone change code has expired.")

        if not challenge.has_attempts_remaining:
            raise ValidationError("Phone change challenge has no attempts remaining.")

        if not check_otp_code(submitted_code, challenge.code_hash):
            challenge.attempts_count += 1
            challenge.save(update_fields=["attempts_count"])
            invalid_code_submitted = True
        else:
            locked_user.phone_number = normalized_phone_number
            locked_user.is_phone_verified = True
            locked_user.save(
                update_fields=[
                    "phone_number",
                    "is_phone_verified",
                    "updated_at",
                ]
            )

            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])

    if invalid_code_submitted:
        raise ValidationError("Invalid phone change code.")

    return PhoneChangeConfirmResult(
        challenge=challenge,
        user=locked_user,
    )
