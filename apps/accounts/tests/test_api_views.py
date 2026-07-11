from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import check_otp_code, create_otp_challenge
from django.test import override_settings


class OTPRequestAPIViewTests(APITestCase):

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
        self.assertIn("refresh", response.data)

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

        response = self.client.post(
            refresh_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotEqual(
            response.data["refresh"],
            verify_response.data["refresh"],
        )

    def test_rejects_invalid_refresh_token(self):
        url = reverse("accounts-api:token-refresh")

        response = self.client.post(
            url,
            data={
                "refresh": "invalid-refresh-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        logout_response = self.client.post(
            logout_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            logout_response.data["detail"],
            "Logged out successfully.",
        )

        refresh_response = self.client.post(
            refresh_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_400_BAD_REQUEST)