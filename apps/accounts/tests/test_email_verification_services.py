from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.services.email_verification import (
    create_email_verification_challenge,
    verify_email_challenge,
)
from apps.accounts.services.otp import check_otp_code


User = get_user_model()


class EmailVerificationServiceTests(TestCase):
    def test_creates_email_verification_challenge(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        result = create_email_verification_challenge(
            user=user,
            email="  Ali@Example.COM  ",
            requested_ip="127.0.0.1",
        )

        challenge = result.challenge

        self.assertEqual(challenge.user_id, user.id)
        self.assertEqual(challenge.email, "ali@example.com")
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertEqual(len(result.plain_code), 6)
        self.assertTrue(result.plain_code.isdigit())
        self.assertNotEqual(challenge.code_hash, result.plain_code)
        self.assertTrue(check_otp_code(result.plain_code, challenge.code_hash))

    def test_revokes_previous_active_challenge_for_same_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        first_result = create_email_verification_challenge(
            user=user,
            email="first@example.com",
        )
        second_result = create_email_verification_challenge(
            user=user,
            email="second@example.com",
        )

        first_result.challenge.refresh_from_db()
        second_result.challenge.refresh_from_db()

        self.assertIsNotNone(first_result.challenge.revoked_at)
        self.assertIsNone(second_result.challenge.revoked_at)

    def test_rejects_email_already_used_by_another_user(self):
        User.objects.create_user(
            phone_number="+989121234567",
            email="taken@example.com",
            is_phone_verified=True,
            is_email_verified=True,
        )
        user = User.objects.create_user(
            phone_number="+989991234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            create_email_verification_challenge(
                user=user,
                email="taken@example.com",
            )

    def test_verifies_email_challenge_and_updates_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_email_verification_challenge(
            user=user,
            email="Ali@Example.COM",
        )

        verification_result = verify_email_challenge(
            user=user,
            email="ali@example.com",
            plain_code=result.plain_code,
        )

        result.challenge.refresh_from_db()
        verification_result.user.refresh_from_db()

        self.assertEqual(verification_result.user.email, "ali@example.com")
        self.assertTrue(verification_result.user.is_email_verified)
        self.assertIsNotNone(result.challenge.used_at)

    def test_rejects_invalid_code_and_increments_attempts_count(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_email_verification_challenge(
            user=user,
            email="ali@example.com",
        )
        invalid_code = "000000" if result.plain_code != "000000" else "111111"

        with self.assertRaises(ValidationError):
            verify_email_challenge(
                user=user,
                email="ali@example.com",
                plain_code=invalid_code,
            )

        result.challenge.refresh_from_db()

        self.assertEqual(result.challenge.attempts_count, 1)
        self.assertIsNone(result.challenge.used_at)

    def test_rejects_expired_challenge(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_email_verification_challenge(
            user=user,
            email="ali@example.com",
        )
        result.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        result.challenge.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            verify_email_challenge(
                user=user,
                email="ali@example.com",
                plain_code=result.plain_code,
            )

    def test_rejects_challenge_without_remaining_attempts(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_email_verification_challenge(
            user=user,
            email="ali@example.com",
        )
        result.challenge.attempts_count = 5
        result.challenge.max_attempts = 5
        result.challenge.save(update_fields=["attempts_count", "max_attempts"])

        with self.assertRaises(ValidationError):
            verify_email_challenge(
                user=user,
                email="ali@example.com",
                plain_code=result.plain_code,
            )

    def test_rejects_when_no_active_challenge_exists(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            verify_email_challenge(
                user=user,
                email="ali@example.com",
                plain_code="123456",
            )