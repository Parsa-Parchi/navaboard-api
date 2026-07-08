from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import (
    check_otp_code,
    create_otp_challenge,
    generate_numeric_otp_code,
    hash_otp_code,
)


class OTPServiceTests(TestCase):
    def test_generates_six_digit_numeric_code(self):
        code = generate_numeric_otp_code()

        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_rejects_too_short_otp_code_length(self):
        with self.assertRaises(ValueError):
            generate_numeric_otp_code(length=3)

    def test_hashes_and_checks_otp_code(self):
        plain_code = "123456"
        encoded_code = hash_otp_code(plain_code)

        self.assertNotEqual(encoded_code, plain_code)
        self.assertTrue(check_otp_code(plain_code, encoded_code))
        self.assertFalse(check_otp_code("000000", encoded_code))

    def test_creates_otp_challenge_with_normalized_phone_number(self):
        before_creation = timezone.now()

        result = create_otp_challenge(
            phone_number="09121234567",
            requested_ip="127.0.0.1",
        )

        challenge = result.challenge

        self.assertEqual(challenge.phone_number, "+989121234567")
        self.assertEqual(challenge.purpose, OTPChallenge.Purpose.LOGIN)
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertEqual(len(result.plain_code), 6)
        self.assertTrue(result.plain_code.isdigit())
        self.assertNotEqual(challenge.code_hash, result.plain_code)
        self.assertTrue(check_otp_code(result.plain_code, challenge.code_hash))
        self.assertGreater(challenge.expires_at, before_creation)

    def test_revokes_previous_active_challenge_for_same_phone_and_purpose(self):
        first_result = create_otp_challenge(phone_number="09121234567")

        second_result = create_otp_challenge(phone_number="+989121234567")

        first_result.challenge.refresh_from_db()

        self.assertIsNotNone(first_result.challenge.revoked_at)
        self.assertIsNone(second_result.challenge.revoked_at)

    def test_does_not_revoke_challenge_for_different_purpose(self):
        login_result = create_otp_challenge(
            phone_number="09121234567",
            purpose=OTPChallenge.Purpose.LOGIN,
        )

        verify_phone_result = create_otp_challenge(
            phone_number="09121234567",
            purpose=OTPChallenge.Purpose.VERIFY_PHONE,
        )

        login_result.challenge.refresh_from_db()
        verify_phone_result.challenge.refresh_from_db()

        self.assertIsNone(login_result.challenge.revoked_at)
        self.assertIsNone(verify_phone_result.challenge.revoked_at)

    def test_rejects_missing_phone_number(self):
        with self.assertRaises(ValidationError):
            create_otp_challenge(phone_number="")