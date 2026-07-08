from django.test import SimpleTestCase

from apps.accounts.api.serializers import OTPRequestSerializer
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