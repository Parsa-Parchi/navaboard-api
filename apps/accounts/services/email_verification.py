from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.services.otp import (
    check_otp_code,
    generate_numeric_otp_code,
    hash_otp_code,
)


EMAIL_VERIFICATION_CODE_LIFETIME = timedelta(minutes=10)


@dataclass(frozen=True)
class EmailVerificationRequestResult:
    challenge: EmailVerificationChallenge
    plain_code: str


@dataclass(frozen=True)
class EmailVerificationResult:
    challenge: EmailVerificationChallenge
    user: Any


def _normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise ValidationError("Email address is required.")

    return normalized_email


def create_email_verification_challenge(
    *,
    user: Any,
    email: str,
    requested_ip: str | None = None,
) -> EmailVerificationRequestResult:
    normalized_email = _normalize_email(email)
    now = timezone.now()

    User = get_user_model()

    if User.objects.filter(email__iexact=normalized_email).exclude(id=user.id).exists():
        raise ValidationError("Email address is already in use.")

    current_user_email = (user.email or "").strip().lower()

    if current_user_email == normalized_email and user.is_email_verified:
        raise ValidationError("Email address is already verified.")

    EmailVerificationChallenge.objects.filter(
        user=user,
        used_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    plain_code = generate_numeric_otp_code()

    challenge = EmailVerificationChallenge.objects.create(
        user=user,
        email=normalized_email,
        code_hash=hash_otp_code(plain_code),
        expires_at=now + EMAIL_VERIFICATION_CODE_LIFETIME,
        requested_ip=requested_ip,
    )

    return EmailVerificationRequestResult(
        challenge=challenge,
        plain_code=plain_code,
    )


def verify_email_challenge(
    *,
    user: Any,
    email: str,
    plain_code: str,
) -> EmailVerificationResult:
    normalized_email = _normalize_email(email)
    submitted_code = plain_code.strip()

    if not submitted_code:
        raise ValidationError("Verification code is required.")

    invalid_code_submitted = False

    with transaction.atomic():
        challenge = (
            EmailVerificationChallenge.objects.select_for_update()
            .filter(
                user=user,
                email__iexact=normalized_email,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if challenge is None:
            raise ValidationError("No active email verification challenge found.")

        if challenge.is_expired:
            raise ValidationError("Email verification code has expired.")

        if not challenge.has_attempts_remaining:
            raise ValidationError(
                "Email verification challenge has no attempts remaining."
            )

        if not check_otp_code(submitted_code, challenge.code_hash):
            challenge.attempts_count += 1
            challenge.save(update_fields=["attempts_count"])
            invalid_code_submitted = True
        else:
            User = get_user_model()

            if (
                User.objects.select_for_update()
                .filter(email__iexact=normalized_email)
                .exclude(id=user.id)
                .exists()
            ):
                raise ValidationError("Email address is already in use.")

            user.email = normalized_email
            user.is_email_verified = True
            user.save(update_fields=["email", "is_email_verified", "updated_at"])

            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])

    if invalid_code_submitted:
        raise ValidationError("Invalid email verification code.")

    return EmailVerificationResult(
        challenge=challenge,
        user=user,
    )