from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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