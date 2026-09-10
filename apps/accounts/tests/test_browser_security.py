from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase, APIClient

from apps.accounts.services.otp import create_login_otp_challenge
from apps.accounts.services.tokens import issue_auth_token_pair


class BrowserSessionTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(phone_number="09121234599", is_phone_verified=True)

    def csrf(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.data["csrfToken"]

    def test_refresh_requires_csrf_and_ignores_expired_access_header(self):
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = issue_auth_token_pair(self.user).refresh
        self.assertEqual(self.client.post("/api/auth/token/refresh/").status_code, 403)
        response = self.client.post("/api/auth/token/refresh/", HTTP_X_CSRFTOKEN=self.csrf(), HTTP_AUTHORIZATION="Bearer invalid")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]["httponly"])

    def test_login_csrf_then_logout_without_access_token(self):
        challenge = create_login_otp_challenge(phone_number=self.user.phone_number)
        data = {"phone_number": self.user.phone_number, "code": challenge.plain_code}
        self.assertEqual(self.client.post("/api/auth/otp/verify/", data).status_code, 403)
        token = self.csrf()
        self.assertEqual(self.client.post("/api/auth/otp/verify/", data, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/token/refresh/", HTTP_X_CSRFTOKEN=token).status_code, 400)

    @override_settings(AUTH_ENABLE_EMAIL_SIGNUP=False)
    def test_email_only_signup_disabled(self):
        for action in ("request", "confirm"):
            self.assertEqual(self.client.post(f"/api/auth/email/signup/{action}/", {}).status_code, 410)

    def test_valid_csrf_does_not_allow_untrusted_origin(self):
        token = self.csrf()
        response = self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://untrusted.invalid")
        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())
