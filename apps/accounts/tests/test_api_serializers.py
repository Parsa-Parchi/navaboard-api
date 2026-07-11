from django.test import SimpleTestCase

from apps.accounts.api.serializers import (
    LogoutRequestSerializer,
    LogoutResponseSerializer,
    OTPRequestSerializer,
    OTPVerificationSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
)
from apps.accounts.models import OTPChallenge


class OTPRequestSerializerTests(SimpleTestCase):
    def test_validates_and_normalizes_phone_number(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "09121234567",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertEqual(
            serializer.validated_data["purpose"],
            OTPChallenge.Purpose.LOGIN,
        )

    def test_accepts_supported_purpose(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "۰۹۱۲۱۲۳۴۵۶۷",
                "purpose": OTPChallenge.Purpose.VERIFY_PHONE,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertEqual(
            serializer.validated_data["purpose"],
            OTPChallenge.Purpose.VERIFY_PHONE,
        )

    def test_rejects_invalid_phone_number(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "02112345678",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_missing_phone_number(self):
        serializer = OTPRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_invalid_purpose(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "09121234567",
                "purpose": "invalid-purpose",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)

class OTPVerificationSerializerTests(SimpleTestCase):
    def test_validates_and_normalizes_phone_number_and_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertEqual(serializer.validated_data["code"], "123456")
        self.assertEqual(
            serializer.validated_data["purpose"],
            OTPChallenge.Purpose.LOGIN,
        )

    def test_accepts_supported_purpose(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "۰۹۱۲۱۲۳۴۵۶۷",
                "code": "123456",
                "purpose": OTPChallenge.Purpose.VERIFY_PHONE,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertEqual(
            serializer.validated_data["purpose"],
            OTPChallenge.Purpose.VERIFY_PHONE,
        )

    def test_rejects_invalid_phone_number(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "02112345678",
                "code": "123456",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_missing_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_non_numeric_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "abcdef",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_short_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_invalid_purpose(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "123456",
                "purpose": "invalid-purpose",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)


class AuthSessionSerializerTests(SimpleTestCase):
    def test_token_refresh_request_accepts_refresh_token(self):
        serializer = TokenRefreshRequestSerializer(
            data={
                "refresh": "refresh-token-value",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["refresh"],
            "refresh-token-value",
        )

    def test_token_refresh_request_rejects_missing_refresh_token(self):
        serializer = TokenRefreshRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("refresh", serializer.errors)

    def test_logout_request_accepts_refresh_token(self):
        serializer = LogoutRequestSerializer(
            data={
                "refresh": "refresh-token-value",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["refresh"],
            "refresh-token-value",
        )

    def test_logout_request_rejects_missing_refresh_token(self):
        serializer = LogoutRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("refresh", serializer.errors)