from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.services.tokens import (
    blacklist_refresh_token,
    issue_auth_token_pair,
    refresh_auth_token_pair,
)


User = get_user_model()


class AuthTokenServiceTests(TestCase):
    def test_issues_access_and_refresh_tokens_for_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        token_pair = issue_auth_token_pair(user)

        access_token = AccessToken(token_pair.access)
        refresh_token = RefreshToken(token_pair.refresh)

        self.assertEqual(str(access_token["user_id"]), str(user.id))
        self.assertEqual(str(refresh_token["user_id"]), str(user.id))

    def test_refreshes_auth_token_pair(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)

        refreshed_token_pair = refresh_auth_token_pair(token_pair.refresh)

        access_token = AccessToken(refreshed_token_pair.access)
        refresh_token = RefreshToken(refreshed_token_pair.refresh)

        self.assertEqual(str(access_token["user_id"]), str(user.id))
        self.assertEqual(str(refresh_token["user_id"]), str(user.id))
        self.assertNotEqual(refreshed_token_pair.refresh, token_pair.refresh)

    def test_rejects_blank_refresh_token_when_refreshing(self):
        with self.assertRaises(ValidationError):
            refresh_auth_token_pair("   ")

    def test_blacklists_refresh_token(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)

        blacklist_refresh_token(token_pair.refresh)

        with self.assertRaises(ValidationError):
            refresh_auth_token_pair(token_pair.refresh)

    def test_rejects_blank_refresh_token_when_blacklisting(self):
        with self.assertRaises(ValidationError):
            blacklist_refresh_token("   ")