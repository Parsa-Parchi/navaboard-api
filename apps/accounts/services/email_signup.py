from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.services.email_verification import (
    create_email_verification_challenge,
    verify_email_challenge,
)

User = get_user_model()


@dataclass(frozen=True)
class EmailSignupRequestResult:
    user: User
    challenge: EmailVerificationChallenge
    plain_code: str
    user_created: bool


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

    existing_user = User.objects.filter(email__iexact=normalized_email).first()

    if existing_user and existing_user.is_email_verified:
        raise ValidationError("Email address is already registered.")

    if existing_user:
        user = existing_user
        validate_password(password, user=user)
        user.full_name = normalized_full_name
        user.set_password(password)
        user.is_active = True
        user.save(
            update_fields=[
                "full_name",
                "password",
                "is_active",
                "updated_at",
            ]
        )
        user_created = False
    else:
        user = User(
            email=normalized_email,
            full_name=normalized_full_name,
            is_email_verified=False,
            is_active=True,
        )
        validate_password(password, user=user)
        user.set_password(password)
        user.full_clean()
        user.save()
        user_created = True

    challenge_result = create_email_verification_challenge(
        user=user,
        email=normalized_email,
        requested_ip=requested_ip,
    )

    return EmailSignupRequestResult(
        user=user,
        challenge=challenge_result.challenge,
        plain_code=challenge_result.plain_code,
        user_created=user_created,
    )


def confirm_email_signup(
    *,
    email: str,
    plain_code: str,
) -> EmailSignupConfirmResult:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise ValidationError("Email address is required.")

    user = User.objects.filter(email__iexact=normalized_email).first()

    if user is None:
        raise ValidationError("Email signup request was not found.")

    if user.is_email_verified:
        raise ValidationError("Email address is already verified.")

    result = verify_email_challenge(
        user=user,
        email=normalized_email,
        plain_code=plain_code,
    )

    return EmailSignupConfirmResult(user=result.user)