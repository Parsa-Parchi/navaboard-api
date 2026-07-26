from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken


@dataclass(frozen=True)
class AuthTokenPair:
    access: str
    refresh: str


def issue_auth_token_pair(user: Any) -> AuthTokenPair:
    refresh_token = RefreshToken.for_user(user)

    return AuthTokenPair(
        access=str(refresh_token.access_token),
        refresh=str(refresh_token),
    )


def refresh_auth_token_pair(refresh_token: str) -> AuthTokenPair:
    normalized_refresh_token = refresh_token.strip()

    if not normalized_refresh_token:
        raise ValidationError("Refresh token is required.")

    serializer = TokenRefreshSerializer(
        data={
            "refresh": normalized_refresh_token,
        }
    )

    try:
        serializer.is_valid(raise_exception=True)
    except TokenError as exc:
        raise ValidationError("Refresh token is invalid or expired.") from exc

    return AuthTokenPair(
        access=serializer.validated_data["access"],
        refresh=serializer.validated_data.get("refresh", normalized_refresh_token),
    )


def blacklist_refresh_token(refresh_token: str) -> None:
    normalized_refresh_token = refresh_token.strip()

    if not normalized_refresh_token:
        raise ValidationError("Refresh token is required.")

    try:
        RefreshToken(normalized_refresh_token).blacklist()
    except TokenError as exc:
        raise ValidationError("Refresh token is invalid or expired.") from exc


def blacklist_all_refresh_tokens_for_user(user: Any) -> None:
    outstanding_tokens = OutstandingToken.objects.filter(user=user)

    for outstanding_token in outstanding_tokens.iterator():
        BlacklistedToken.objects.get_or_create(token=outstanding_token)
