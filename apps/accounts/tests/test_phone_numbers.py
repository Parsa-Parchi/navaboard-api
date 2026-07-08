from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.accounts.phone_numbers import normalize_iranian_mobile_number


class IranianMobileNumberNormalizationTests(SimpleTestCase):
    def test_normalizes_supported_iranian_mobile_formats(self):
        cases = {
            "09121234567": "+989121234567",
            "9121234567": "+989121234567",
            "989121234567": "+989121234567",
            "+989121234567": "+989121234567",
            "00989121234567": "+989121234567",
            "۰۹۱۲۱۲۳۴۵۶۷": "+989121234567",
            "٠٩١٢١٢٣٤٥٦٧": "+989121234567",
            "(0912) 123-4567": "+989121234567",
        }

        for raw_phone_number, expected_phone_number in cases.items():
            with self.subTest(raw_phone_number=raw_phone_number):
                self.assertEqual(
                    normalize_iranian_mobile_number(raw_phone_number),
                    expected_phone_number,
                )

    def test_returns_none_for_missing_or_blank_phone_number(self):
        self.assertIsNone(normalize_iranian_mobile_number(None))
        self.assertIsNone(normalize_iranian_mobile_number(""))
        self.assertIsNone(normalize_iranian_mobile_number("   "))

    def test_rejects_invalid_iranian_mobile_numbers(self):
        invalid_phone_numbers = [
            "02112345678",
            "+982112345678",
            "0912123456",
            "091212345678",
            "+98912123456",
            "+9891212345678",
            "hello",
        ]

        for raw_phone_number in invalid_phone_numbers:
            with self.subTest(raw_phone_number=raw_phone_number):
                with self.assertRaises(ValidationError):
                    normalize_iranian_mobile_number(raw_phone_number)