from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import EmailSignupChallenge
from apps.accounts.services.email_verification import (
    EMAIL_VERIFICATION_CODE_LIFETIME,
)
from apps.accounts.services.otp import (
    check_otp_code,
    generate_numeric_otp_code,
    hash_otp_code,
)

User = get_user_model()


@dataclass(frozen=True)
class EmailSignupRequestResult:
    challenge: EmailSignupChallenge
    plain_code: str


@dataclass(frozen=True)
class EmailSignupConfirmResult:
    user: User


def create_email_signup_challenge(
    *,
    email: str,
    password: str,
    full_name: str = "",
    requested_ip: str | None = None,
) -> EmailSignupRequestResult:
    normalized_email = email.strip().lower()
    normalized_full_name = full_name.strip()

    if not normalized_email:
        raise ValidationError("Email address is required.")

    if not password:
        raise ValidationError("Password is required.")

    if User.objects.filter(email__iexact=normalized_email).exists():
        raise ValidationError("Email address is already registered.")

    prospective_user = User(
        email=normalized_email,
        full_name=normalized_full_name,
    )
    validate_password(password, user=prospective_user)
    now = timezone.now()

    try:
        with transaction.atomic():
            EmailSignupChallenge.objects.filter(
                email__iexact=normalized_email,
                used_at__isnull=True,
                revoked_at__isnull=True,
            ).update(
                revoked_at=now,
                password_hash="",
            )

            plain_code = generate_numeric_otp_code()
            challenge = EmailSignupChallenge.objects.create(
                email=normalized_email,
                full_name=normalized_full_name,
                password_hash=make_password(password),
                code_hash=hash_otp_code(plain_code),
                expires_at=now + EMAIL_VERIFICATION_CODE_LIFETIME,
                requested_ip=requested_ip,
            )
    except IntegrityError as exc:
        raise ValidationError(
            "An email signup request is already being processed."
        ) from exc

    return EmailSignupRequestResult(
        challenge=challenge,
        plain_code=plain_code,
    )


def confirm_email_signup(
    *,
    email: str,
    plain_code: str,
) -> EmailSignupConfirmResult:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise ValidationError("Email address is required.")

    submitted_code = plain_code.strip()

    if not submitted_code:
        raise ValidationError("Verification code is required.")

    invalid_code_submitted = False

    try:
        with transaction.atomic():
            challenge = (
                EmailSignupChallenge.objects.select_for_update()
                .filter(
                    email__iexact=normalized_email,
                    used_at__isnull=True,
                    revoked_at__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )

            if challenge is None:
                raise ValidationError("Email signup request was not found.")

            if challenge.is_expired:
                raise ValidationError(
                    "Email signup verification code has expired."
                )

            if not challenge.has_attempts_remaining:
                raise ValidationError(
                    "Email signup challenge has no attempts remaining."
                )

            if not check_otp_code(submitted_code, challenge.code_hash):
                challenge.attempts_count += 1
                challenge.save(update_fields=["attempts_count"])
                invalid_code_submitted = True
            else:
                if User.objects.filter(
                    email__iexact=normalized_email,
                ).exists():
                    raise ValidationError("Email address is already registered.")

                user = User(
                    email=normalized_email,
                    full_name=challenge.full_name,
                    is_email_verified=True,
                    is_active=True,
                    password=challenge.password_hash,
                )
                user.full_clean()
                user.save()

                challenge.used_at = timezone.now()
                challenge.password_hash = ""
                challenge.save(update_fields=["used_at", "password_hash"])
    except IntegrityError as exc:
        raise ValidationError("Email address is already registered.") from exc

    if invalid_code_submitted:
        raise ValidationError("Invalid email signup verification code.")

    return EmailSignupConfirmResult(user=user)
