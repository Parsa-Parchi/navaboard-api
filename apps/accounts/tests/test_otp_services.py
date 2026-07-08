from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import (
    check_otp_code,
    create_otp_challenge,
    generate_numeric_otp_code,
    hash_otp_code,
    verify_otp_challenge,
)
from datetime import timedelta


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


    def test_verifies_otp_and_creates_user_for_new_phone_number(self):
        request_result = create_otp_challenge(phone_number="09121234567")

        verification_result = verify_otp_challenge(
            phone_number="+989121234567",
            plain_code=request_result.plain_code,
        )

        request_result.challenge.refresh_from_db()

        self.assertTrue(verification_result.user_created)
        self.assertEqual(verification_result.user.phone_number, "+989121234567")
        self.assertTrue(verification_result.user.is_phone_verified)
        self.assertIsNotNone(request_result.challenge.used_at)

    def test_verifies_otp_and_uses_existing_user(self):
        request_result = create_otp_challenge(phone_number="09121234567")

        first_verification_result = verify_otp_challenge(
            phone_number="09121234567",
            plain_code=request_result.plain_code,
        )

        second_request_result = create_otp_challenge(phone_number="09121234567")

        second_verification_result = verify_otp_challenge(
            phone_number="09121234567",
            plain_code=second_request_result.plain_code,
        )

        self.assertTrue(first_verification_result.user_created)
        self.assertFalse(second_verification_result.user_created)
        self.assertEqual(
            first_verification_result.user.id,
            second_verification_result.user.id,
        )

    def test_marks_existing_user_phone_as_verified(self):
        request_result = create_otp_challenge(phone_number="09121234567")

        verification_result = verify_otp_challenge(
            phone_number="09121234567",
            plain_code=request_result.plain_code,
        )

        user = verification_result.user
        user.is_phone_verified = False
        user.save(update_fields=["is_phone_verified"])

        second_request_result = create_otp_challenge(phone_number="09121234567")

        second_verification_result = verify_otp_challenge(
            phone_number="09121234567",
            plain_code=second_request_result.plain_code,
        )

        second_verification_result.user.refresh_from_db()

        self.assertFalse(second_verification_result.user_created)
        self.assertTrue(second_verification_result.user.is_phone_verified)

    def test_rejects_invalid_otp_code_and_increments_attempts_count(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        invalid_code = (
            "000000"
            if request_result.plain_code != "000000"
            else "111111"
        )

        with self.assertRaises(ValidationError):
            verify_otp_challenge(
                phone_number="09121234567",
                plain_code=invalid_code,
            )

        request_result.challenge.refresh_from_db()

        self.assertEqual(request_result.challenge.attempts_count, 1)
        self.assertIsNone(request_result.challenge.used_at)


    def test_rejects_expired_otp_challenge(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        request_result.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        request_result.challenge.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            verify_otp_challenge(
                phone_number="09121234567",
                plain_code=request_result.plain_code,
            )

    def test_rejects_otp_challenge_without_remaining_attempts(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        request_result.challenge.attempts_count = 5
        request_result.challenge.max_attempts = 5
        request_result.challenge.save(update_fields=["attempts_count", "max_attempts"])

        with self.assertRaises(ValidationError):
            verify_otp_challenge(
                phone_number="09121234567",
                plain_code=request_result.plain_code,
            )

    def test_rejects_when_no_active_otp_challenge_exists(self):
        with self.assertRaises(ValidationError):
            verify_otp_challenge(
                phone_number="09121234567",
                plain_code="123456",
            )

    def test_rejects_missing_otp_code(self):
        create_otp_challenge(phone_number="09121234567")

        with self.assertRaises(ValidationError):
            verify_otp_challenge(
                phone_number="09121234567",
                plain_code="   ",
            )