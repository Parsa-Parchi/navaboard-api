from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def set_initial_password_for_user(
    *,
    user: Any,
    password: str,
) -> Any:
    if not password:
        raise ValidationError("Password is required.")

    if user.has_usable_password():
        raise ValidationError("Password is already set for this account.")

    validate_password(password, user=user)

    user.set_password(password)
    user.save(update_fields=["password", "updated_at"])

    return user