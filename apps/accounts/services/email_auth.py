from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


def authenticate_with_email_and_password(
    *,
    email: str,
    password: str,
) -> Any:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise ValidationError("Email address is required.")

    if not password:
        raise ValidationError("Password is required.")

    User = get_user_model()

    try:
        user = User.objects.get(email__iexact=normalized_email)
    except User.DoesNotExist as exc:
        raise ValidationError("Invalid email or password.") from exc

    if not user.is_active:
        raise ValidationError("User account is inactive.")

    if not user.is_email_verified:
        raise ValidationError("Email address is not verified.")

    if not user.has_usable_password():
        raise ValidationError("Password login is not enabled for this account.")

    if not user.check_password(password):
        raise ValidationError("Invalid email or password.")

    return user