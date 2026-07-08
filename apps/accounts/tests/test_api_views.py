from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import check_otp_code
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