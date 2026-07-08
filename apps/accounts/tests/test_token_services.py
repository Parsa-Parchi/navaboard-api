from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.services.tokens import issue_auth_token_pair


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