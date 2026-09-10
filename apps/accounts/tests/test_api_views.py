from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.accounts.api.throttles import (
    EmailCodeRequestEmailThrottle,
    EmailCodeRequestIPThrottle,
    EmailCodeVerificationEmailThrottle,
    EmailCodeVerificationIPThrottle,
    EmailLoginEmailThrottle,
    EmailLoginIPThrottle,
    OTPRequestIPThrottle,
    OTPRequestPhoneThrottle,
    OTPVerificationIPThrottle,
    OTPVerificationPhoneThrottle,
    PasswordMutationUserThrottle,
    TokenRefreshIPThrottle,
)
from apps.accounts.models import (
    EmailSignupChallenge,
    EmailVerificationChallenge,
    OTPChallenge,
)
from apps.accounts.services.email_signup import create_email_signup_challenge
from apps.accounts.services.otp import check_otp_code, create_otp_challenge
from apps.accounts.services.tokens import issue_auth_token_pair


from django.contrib.auth import get_user_model


User = get_user_model()

class OTPRequestAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_requests_otp_code(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "OTP code has been generated.")
        self.assertIn("expires_at", response.data)
        self.assertIn("development_otp_code", response.data)

        challenge = OTPChallenge.objects.get()

        self.assertEqual(challenge.phone_number, "+989121234567")
        self.assertEqual(challenge.purpose, OTPChallenge.Purpose.LOGIN)
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertTrue(
            check_otp_code(
                response.data["development_otp_code"],
                challenge.code_hash,
            )
        )

    def test_rejects_invalid_phone_number(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "02112345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)

    def test_rejects_client_supplied_purpose(self):
        response = self.client.post(
            reverse("accounts-api:otp-request"),
            data={
                "phone_number": "09121234567",
                "purpose": OTPChallenge.Purpose.PASSWORD_RESET,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("purpose", response.data)
        self.assertFalse(OTPChallenge.objects.exists())

    @patch.object(OTPRequestIPThrottle, "rate", "100/minute", create=True)
    @patch.object(OTPRequestPhoneThrottle, "rate", "2/minute", create=True)
    def test_throttles_repeated_requests_for_same_phone_number(self):
        url = reverse("accounts-api:otp-request")

        responses = [
            self.client.post(
                url,
                data={"phone_number": "09121234567"},
                format="json",
            )
            for _ in range(3)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertEqual(OTPChallenge.objects.count(), 2)
        self.assertIn("Retry-After", responses[-1])

    @patch.object(OTPRequestIPThrottle, "rate", "2/minute", create=True)
    @patch.object(OTPRequestPhoneThrottle, "rate", "100/minute", create=True)
    def test_throttles_by_remote_ip_and_ignores_spoofed_forwarded_for(self):
        url = reverse("accounts-api:otp-request")
        phone_numbers = [
            "09120000001",
            "09120000002",
            "09120000003",
        ]

        responses = [
            self.client.post(
                url,
                data={"phone_number": phone_number},
                format="json",
                HTTP_X_FORWARDED_FOR=f"203.0.113.{index}",
            )
            for index, phone_number in enumerate(phone_numbers, start=1)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_revokes_previous_active_challenge(self):
        url = reverse("accounts-api:otp-request")

        first_response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )
        second_response = self.client.post(
            url,
            data={
                "phone_number": "+989121234567",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        challenges = OTPChallenge.objects.order_by("created_at")
        self.assertEqual(challenges.count(), 2)
        self.assertIsNotNone(challenges[0].revoked_at)
        self.assertIsNone(challenges[1].revoked_at)


    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_does_not_expose_development_otp_code_when_disabled(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("expires_at", response.data)
        self.assertNotIn("development_otp_code", response.data)


class OTPVerificationAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_verifies_otp_and_returns_tokens_for_new_user(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertTrue(response.data["user_created"])
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, response.cookies)
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value)

        user_data = response.data["user"]
        self.assertEqual(user_data["phone_number"], "+989121234567")
        self.assertTrue(user_data["is_phone_verified"])

        request_result.challenge.refresh_from_db()
        self.assertIsNotNone(request_result.challenge.used_at)

    def test_verifies_otp_and_returns_existing_user(self):
        first_request_result = create_otp_challenge(phone_number="09121234567")
        url = reverse("accounts-api:otp-verify")

        first_response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": first_request_result.plain_code,
            },
            format="json",
        )

        second_request_result = create_otp_challenge(phone_number="09121234567")

        second_response = self.client.post(
            url,
            data={
                "phone_number": "+989121234567",
                "code": second_request_result.plain_code,
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data["user_created"])
        self.assertFalse(second_response.data["user_created"])
        self.assertEqual(
            first_response.data["user"]["id"],
            second_response.data["user"]["id"],
        )

    def test_rejects_invalid_otp_code(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        invalid_code = (
            "000000"
            if request_result.plain_code != "000000"
            else "111111"
        )
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": invalid_code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_client_supplied_purpose(self):
        request_result = create_otp_challenge(phone_number="09121234567")

        response = self.client.post(
            reverse("accounts-api:otp-verify"),
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
                "purpose": OTPChallenge.Purpose.PASSWORD_RESET,
            },
            format="json",
        )

        request_result.challenge.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("purpose", response.data)
        self.assertIsNone(request_result.challenge.used_at)

    @patch.object(OTPVerificationIPThrottle, "rate", "100/minute", create=True)
    @patch.object(
        OTPVerificationPhoneThrottle,
        "rate",
        "2/minute",
        create=True,
    )
    def test_throttles_repeated_verification_attempts_for_same_phone_number(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        invalid_code = (
            "000000"
            if request_result.plain_code != "000000"
            else "111111"
        )
        url = reverse("accounts-api:otp-verify")

        responses = [
            self.client.post(
                url,
                data={
                    "phone_number": "09121234567",
                    "code": invalid_code,
                },
                format="json",
            )
            for _ in range(3)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_rejects_missing_active_challenge(self):
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class AuthSessionAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_refreshes_auth_tokens(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        refresh_url = reverse("accounts-api:token-refresh")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        initial_refresh_cookie = verify_response.cookies[
            settings.AUTH_REFRESH_COOKIE_NAME
        ].value

        response = self.client.post(
            refresh_url,
            data={},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, response.cookies)
        self.assertNotEqual(
            response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value,
            initial_refresh_cookie,
        )

    def test_rejects_invalid_refresh_token(self):
        url = reverse("accounts-api:token-refresh")

        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = "invalid-refresh-token"

        response = self.client.post(
            url,
            data={},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(TokenRefreshIPThrottle, "rate", "2/minute", create=True)
    def test_throttles_token_refresh_by_ip(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = token_pair.refresh
        url = reverse("accounts-api:token-refresh")

        responses = [
            self.client.post(url, data={}, format="json")
            for _ in range(3)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_200_OK,
                status.HTTP_200_OK,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertIn("Retry-After", responses[-1])

    def test_logs_out_by_blacklisting_refresh_token(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        logout_url = reverse("accounts-api:logout")
        refresh_url = reverse("accounts-api:token-refresh")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        logout_response = self.client.post(
            logout_url,
            data={},
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            logout_response.data["detail"],
            "Logged out successfully.",
        )
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, logout_response.cookies)

        self.client.credentials()

        refresh_response = self.client.post(
            refresh_url,
            data={},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_400_BAD_REQUEST)

class CurrentUserProfileAPIViewTests(APITestCase):
    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:me")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_current_user_profile(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.get(me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "+989121234567")
        self.assertTrue(response.data["is_phone_verified"])
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)

    def test_updates_current_user_full_name(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.patch(
            me_url,
            data={
                "full_name": "  Ali Test  ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "Ali Test")

    def test_put_updates_current_user_profile(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            full_name="Old Name",
        )
        token_pair = issue_auth_token_pair(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        url = reverse("accounts-api:me")

        response = self.client.put(
            url,
            data={
                "full_name": "New Name",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "New Name")

        user.refresh_from_db()

        self.assertEqual(user.full_name, "New Name")

    def test_does_not_update_read_only_identity_fields(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.patch(
            me_url,
            data={
                "phone_number": "+989991234567",
                "email": "new@example.com",
                "is_phone_verified": False,
                "full_name": "Ali Updated",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "+989121234567")
        self.assertIsNone(response.data["email"])
        self.assertTrue(response.data["is_phone_verified"])
        self.assertEqual(response.data["full_name"], "Ali Updated")


class EmailPasswordLoginAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_logs_in_verified_user_with_email_and_password(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ALI@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertFalse(response.data["user_created"])
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, response.cookies)
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value)
        self.assertEqual(str(response.data["user"]["id"]), str(user.id))
        self.assertEqual(response.data["user"]["email"], "ali@example.com")

    def test_rejects_wrong_password(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_unverified_email(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=False,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_account_without_password_login_enabled(self):
        User.objects.create_user(
            email="ali@example.com",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(EmailLoginIPThrottle, "rate", "100/minute", create=True)
    @patch.object(EmailLoginEmailThrottle, "rate", "2/minute", create=True)
    def test_throttles_login_attempts_for_normalized_email(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")
        emails = [
            "ali@example.com",
            "ALI@example.com",
            "  Ali@Example.COM  ",
        ]

        responses = [
            self.client.post(
                url,
                data={
                    "email": email,
                    "password": "WrongPassword123!",
                },
                format="json",
            )
            for email in emails
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertIn("Retry-After", responses[-1])


@override_settings(AUTH_ENABLE_EMAIL_SIGNUP=True)
class EmailSignupAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_requests_email_signup_code_without_creating_user(self):
        url = reverse("accounts-api:email-signup-request")

        response = self.client.post(
            url,
            data={
                "email": "Ali@Example.COM",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Email signup verification code has been generated.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_email_verification_code", response.data)
        self.assertFalse(User.objects.exists())

        challenge = EmailSignupChallenge.objects.get()

        self.assertEqual(challenge.email, "ali@example.com")
        self.assertEqual(challenge.full_name, "Ali Test")
        self.assertIsNone(challenge.used_at)
        self.assertIsNone(challenge.revoked_at)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_does_not_expose_development_email_signup_code_when_disabled(self):
        url = reverse("accounts-api:email-signup-request")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_email_verification_code", response.data)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirms_email_signup_and_logs_user_in(self):
        request_url = reverse("accounts-api:email-signup-request")
        confirm_url = reverse("accounts-api:email-signup-confirm")

        request_response = self.client.post(
            request_url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        response = self.client.post(
            confirm_url,
            data={
                "email": "ali@example.com",
                "code": request_response.data[
                    "development_email_verification_code"
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "ali@example.com")
        self.assertEqual(response.data["user"]["full_name"], "Ali Test")
        self.assertFalse(response.data["user"]["is_phone_verified"])
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, response.cookies)
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value)

        user = User.objects.get(email="ali@example.com")

        self.assertTrue(user.is_email_verified)

        challenge = EmailSignupChallenge.objects.get()

        self.assertIsNotNone(challenge.used_at)
        self.assertEqual(challenge.password_hash, "")

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_rejects_invalid_email_signup_code(self):
        request_url = reverse("accounts-api:email-signup-request")
        confirm_url = reverse("accounts-api:email-signup-confirm")

        request_response = self.client.post(
            request_url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        valid_code = request_response.data[
            "development_email_verification_code"
        ]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            confirm_url,
            data={
                "email": "ali@example.com",
                "code": invalid_code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertFalse(User.objects.exists())

    def test_rejects_already_verified_email(self):
        user = User(
            email="ali@example.com",
            full_name="Existing User",
            is_email_verified=True,
            is_active=True,
        )
        user.set_password("StrongPassword123!")
        user.save()

        url = reverse("accounts-api:email-signup-request")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "AnotherStrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(EmailSignupChallenge.objects.count(), 0)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_reissues_code_without_persisting_unverified_user_data(self):
        url = reverse("accounts-api:email-signup-request")

        first_response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            },
            format="json",
        )

        second_response = self.client.post(
            url,
            data={
                "email": "ALI@example.com",
                "password": "NewStrongPassword123!",
                "full_name": "Ali Updated",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(User.objects.exists())

        challenges = EmailSignupChallenge.objects.order_by("created_at")

        self.assertEqual(challenges.count(), 2)
        self.assertIsNotNone(challenges[0].revoked_at)
        self.assertEqual(challenges[0].password_hash, "")
        self.assertIsNone(challenges[1].revoked_at)

        confirm_response = self.client.post(
            reverse("accounts-api:email-signup-confirm"),
            data={
                "email": "ali@example.com",
                "code": second_response.data[
                    "development_email_verification_code"
                ],
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        user = User.objects.get(email="ali@example.com")

        self.assertEqual(user.full_name, "Ali Updated")
        self.assertTrue(user.check_password("NewStrongPassword123!"))

    def test_does_not_reactivate_inactive_existing_account(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="OriginalStrongPassword123!",
            full_name="Original Name",
            is_email_verified=False,
            is_active=False,
        )

        response = self.client.post(
            reverse("accounts-api:email-signup-request"),
            data={
                "email": "ali@example.com",
                "password": "AttackerStrongPassword123!",
                "full_name": "Attacker Name",
            },
            format="json",
        )

        user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(user.is_active)
        self.assertEqual(user.full_name, "Original Name")
        self.assertTrue(user.check_password("OriginalStrongPassword123!"))
        self.assertFalse(EmailSignupChallenge.objects.exists())

    @patch.object(
        EmailCodeRequestIPThrottle,
        "rate",
        "100/minute",
        create=True,
    )
    @patch.object(
        EmailCodeRequestEmailThrottle,
        "rate",
        "2/minute",
        create=True,
    )
    def test_throttles_signup_requests_for_normalized_email(self):
        url = reverse("accounts-api:email-signup-request")
        emails = [
            "ali@example.com",
            "ALI@example.com",
            "  Ali@Example.COM  ",
        ]

        responses = [
            self.client.post(
                url,
                data={
                    "email": email,
                    "password": "StrongPassword123!",
                },
                format="json",
            )
            for email in emails
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertEqual(EmailSignupChallenge.objects.count(), 2)

    @patch.object(
        EmailCodeVerificationIPThrottle,
        "rate",
        "100/minute",
        create=True,
    )
    @patch.object(
        EmailCodeVerificationEmailThrottle,
        "rate",
        "2/minute",
        create=True,
    )
    def test_throttles_signup_confirmation_attempts_by_email(self):
        signup_result = create_email_signup_challenge(
            email="ali@example.com",
            password="StrongPassword123!",
        )
        invalid_code = (
            "000000"
            if signup_result.plain_code != "000000"
            else "111111"
        )
        url = reverse("accounts-api:email-signup-confirm")

        responses = [
            self.client.post(
                url,
                data={
                    "email": "ALI@example.com",
                    "code": invalid_code,
                },
                format="json",
            )
            for _ in range(3)
        ]

        signup_result.challenge.refresh_from_db()

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )
        self.assertEqual(signup_result.challenge.attempts_count, 2)


class SetInitialPasswordAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_sets_initial_password_for_authenticated_user(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        set_password_url = reverse("accounts-api:set-password")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.post(
            set_password_url,
            data={
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been set successfully. Please sign in again.",
        )
        self.assertEqual(
            response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value,
            "",
        )

        user = User.objects.get(phone_number="+989121234567")
        self.assertTrue(user.check_password("StrongPassword123!"))

        profile_response = self.client.get(
            reverse("accounts-api:me"),
        )

        self.assertEqual(
            profile_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:set-password")

        response = self.client.post(
            url,
            data={
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_setting_password_when_password_already_exists(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="StrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:set-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "password": "AnotherStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class ChangePasswordAPIViewTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_changes_password_for_authenticated_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = token_pair.refresh
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been changed successfully. Please sign in again.",
        )

        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPassword123!"))
        self.assertFalse(user.check_password("OldStrongPassword123!"))
        self.assertEqual(
            response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value,
            "",
        )

        profile_response = self.client.get(
            reverse("accounts-api:me"),
        )

        self.assertEqual(
            profile_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.client.credentials()
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = token_pair.refresh
        refresh_response = self.client.post(
            reverse("accounts-api:token-refresh"),
            data={},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:change-password")

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_wrong_current_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "WrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_user_without_existing_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(
        PasswordMutationUserThrottle,
        "rate",
        "2/hour",
        create=True,
    )
    def test_throttles_password_change_attempts_by_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )
        url = reverse("accounts-api:change-password")

        responses = [
            self.client.post(
                url,
                data={
                    "current_password": "WrongPassword123!",
                    "new_password": "NewStrongPassword123!",
                },
                format="json",
            )
            for _ in range(3)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )


class EmailVerificationAPIViewTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_request_email_verification_code(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "  Ali@Example.COM  ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Email verification code has been created.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_verification_code", response.data)

        challenge = EmailVerificationChallenge.objects.get(user=self.user)

        self.assertEqual(challenge.email, "ali@example.com")
        self.assertEqual(len(response.data["development_verification_code"]), 6)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_request_response_hides_development_code_when_disabled(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_verification_code", response.data)

    @patch.object(
        EmailCodeRequestIPThrottle,
        "rate",
        "100/minute",
        create=True,
    )
    @patch.object(
        EmailCodeRequestEmailThrottle,
        "rate",
        "2/minute",
        create=True,
    )
    def test_throttles_authenticated_email_verification_requests(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("accounts-api:email-verification-request")

        responses = [
            self.client.post(
                url,
                {
                    "email": email,
                },
                format="json",
            )
            for email in (
                "ali@example.com",
                "ALI@example.com",
                "  Ali@Example.COM  ",
            )
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_anonymous_user_cannot_request_email_verification_code(self):
        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_confirm_email_verification_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "Ali@Example.COM",
            },
            format="json",
        )

        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": request_response.data["development_verification_code"],
            },
            format="json",
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Email address has been verified successfully.",
        )
        self.assertEqual(response.data["email"], "ali@example.com")
        self.assertTrue(response.data["is_email_verified"])
        self.assertEqual(self.user.email, "ali@example.com")
        self.assertTrue(self.user.is_email_verified)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirm_rejects_invalid_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        valid_code = request_response.data["development_verification_code"]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": invalid_code,
            },
            format="json",
        )

        challenge = EmailVerificationChallenge.objects.get(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 1)
        self.assertIsNone(challenge.used_at)

    def test_anonymous_user_cannot_confirm_email_verification_code(self):
        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class PasswordResetAPIViewTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_user_can_request_password_reset_code(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "0912 123 4567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Password reset code has been created.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_otp_code", response.data)

        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(challenge.phone_number, self.user.phone_number)
        self.assertEqual(len(response.data["development_otp_code"]), 6)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_request_response_hides_development_code_when_disabled(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_otp_code", response.data)

    @patch.object(OTPRequestIPThrottle, "rate", "100/minute", create=True)
    @patch.object(OTPRequestPhoneThrottle, "rate", "2/minute", create=True)
    def test_throttles_password_reset_requests_by_phone(self):
        url = reverse("accounts-api:password-reset-request")

        responses = [
            self.client.post(
                url,
                {
                    "phone_number": phone_number,
                },
                format="json",
            )
            for phone_number in (
                "0912 123 4567",
                "+989121234567",
                "09121234567",
            )
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [
                status.HTTP_201_CREATED,
                status.HTTP_201_CREATED,
                status.HTTP_429_TOO_MANY_REQUESTS,
            ],
        )

    def test_rejects_password_reset_request_for_unknown_phone_number(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989991234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_user_can_confirm_password_reset_code(self):
        token_pair = issue_auth_token_pair(self.user)
        request_response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "0912 123 4567",
                "code": request_response.data["development_otp_code"],
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.user.refresh_from_db()
        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been reset successfully. Please sign in again.",
        )
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        self.assertIsNotNone(challenge.used_at)
        self.assertEqual(
            response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value,
            "",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )
        profile_response = self.client.get(
            reverse("accounts-api:me"),
        )

        self.assertEqual(
            profile_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.client.credentials()
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = token_pair.refresh
        refresh_response = self.client.post(
            reverse("accounts-api:token-refresh"),
            data={},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirm_rejects_invalid_code(self):
        request_response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        valid_code = request_response.data["development_otp_code"]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "+989121234567",
                "code": invalid_code,
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 1)
        self.assertIsNone(challenge.used_at)

    def test_confirm_rejects_when_no_active_challenge_exists(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "+989121234567",
                "code": "123456",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PhoneChangeAPIViewTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_request_phone_change_code(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "0912 444 5566",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Phone change code has been created.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_otp_code", response.data)

        challenge = OTPChallenge.objects.get(
            phone_number="+989124445566",
            purpose=OTPChallenge.Purpose.CHANGE_PHONE,
        )

        self.assertEqual(challenge.phone_number, "+989124445566")
        self.assertEqual(challenge.requested_by, self.user)
        self.assertEqual(len(response.data["development_otp_code"]), 6)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_request_response_hides_development_code_when_disabled(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "+989124445566",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_otp_code", response.data)

    def test_anonymous_user_cannot_request_phone_change_code(self):
        response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "+989124445566",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_confirm_phone_change_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "+989124445566",
            },
            format="json",
        )

        response = self.client.post(
            reverse("accounts-api:phone-change-confirm"),
            {
                "phone_number": "0912 444 5566",
                "code": request_response.data["development_otp_code"],
            },
            format="json",
        )

        self.user.refresh_from_db()
        challenge = OTPChallenge.objects.get(
            phone_number="+989124445566",
            purpose=OTPChallenge.Purpose.CHANGE_PHONE,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Phone number has been changed successfully.",
        )
        self.assertEqual(response.data["phone_number"], "+989124445566")
        self.assertTrue(response.data["is_phone_verified"])
        self.assertEqual(self.user.phone_number, "+989124445566")
        self.assertTrue(self.user.is_phone_verified)
        self.assertIsNotNone(challenge.used_at)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirm_rejects_invalid_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "+989124445566",
            },
            format="json",
        )

        valid_code = request_response.data["development_otp_code"]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            reverse("accounts-api:phone-change-confirm"),
            {
                "phone_number": "+989124445566",
                "code": invalid_code,
            },
            format="json",
        )

        challenge = OTPChallenge.objects.get(
            phone_number="+989124445566",
            purpose=OTPChallenge.Purpose.CHANGE_PHONE,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 1)
        self.assertIsNone(challenge.used_at)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_user_cannot_confirm_another_users_phone_change_code(self):
        self.client.force_authenticate(user=self.user)
        request_response = self.client.post(
            reverse("accounts-api:phone-change-request"),
            {
                "phone_number": "+989124445566",
            },
            format="json",
        )
        other_user = User.objects.create_user(
            phone_number="+989131234567",
            is_phone_verified=True,
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.post(
            reverse("accounts-api:phone-change-confirm"),
            {
                "phone_number": "+989124445566",
                "code": request_response.data["development_otp_code"],
            },
            format="json",
        )

        challenge = OTPChallenge.objects.get(
            phone_number="+989124445566",
            purpose=OTPChallenge.Purpose.CHANGE_PHONE,
        )
        other_user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 0)
        self.assertIsNone(challenge.used_at)
        self.assertEqual(other_user.phone_number, "+989131234567")

    def test_anonymous_user_cannot_confirm_phone_change_code(self):
        response = self.client.post(
            reverse("accounts-api:phone-change-confirm"),
            {
                "phone_number": "+989124445566",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
