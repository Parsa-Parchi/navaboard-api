from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.services.tokens import blacklist_all_refresh_tokens_for_user


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

    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        blacklist_all_refresh_tokens_for_user(user)

    return user

def change_password_for_user(
    *,
    user: Any,
    current_password: str,
    new_password: str,
) -> Any:
    if not current_password:
        raise ValidationError("Current password is required.")

    if not new_password:
        raise ValidationError("New password is required.")

    if not user.has_usable_password():
        raise ValidationError("Password is not set for this account.")

    if not user.check_password(current_password):
        raise ValidationError("Current password is incorrect.")

    validate_password(new_password, user=user)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        blacklist_all_refresh_tokens_for_user(user)

    return user
