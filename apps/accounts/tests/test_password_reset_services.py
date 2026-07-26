from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import check_otp_code
from apps.accounts.services.password_reset import (
    confirm_password_reset,
    create_password_reset_challenge,
)
from apps.accounts.services.tokens import (
    issue_auth_token_pair,
    refresh_auth_token_pair,
)


User = get_user_model()


class PasswordResetServiceTests(TestCase):
    def test_creates_password_reset_challenge_for_verified_phone_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

        result = create_password_reset_challenge(
            phone_number="09121234567",
            requested_ip="127.0.0.1",
        )

        challenge = result.challenge

        self.assertEqual(challenge.phone_number, user.phone_number)
        self.assertEqual(challenge.purpose, OTPChallenge.Purpose.PASSWORD_RESET)
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertEqual(len(result.plain_code), 6)
        self.assertTrue(result.plain_code.isdigit())
        self.assertNotEqual(challenge.code_hash, result.plain_code)
        self.assertTrue(check_otp_code(result.plain_code, challenge.code_hash))

    def test_rejects_password_reset_request_for_unknown_phone_number(self):
        with self.assertRaises(ValidationError):
            create_password_reset_challenge(
                phone_number="+989121234567",
            )

    def test_rejects_password_reset_request_for_unverified_phone_user(self):
        User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=False,
        )

        with self.assertRaises(ValidationError):
            create_password_reset_challenge(
                phone_number="+989121234567",
            )

    def test_confirms_password_reset_and_updates_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        result = create_password_reset_challenge(
            phone_number="+989121234567",
        )
        token_pair = issue_auth_token_pair(user)

        confirm_result = confirm_password_reset(
            phone_number="+989121234567",
            plain_code=result.plain_code,
            new_password="NewStrongPassword123!",
        )

        user.refresh_from_db()
        result.challenge.refresh_from_db()

        self.assertEqual(confirm_result.user.id, user.id)
        self.assertTrue(user.check_password("NewStrongPassword123!"))
        self.assertIsNotNone(result.challenge.used_at)

        with self.assertRaises(ValidationError):
            refresh_auth_token_pair(token_pair.refresh)

    def test_rejects_invalid_code_and_increments_attempts_count(self):
        User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        result = create_password_reset_challenge(
            phone_number="+989121234567",
        )
        invalid_code = "000000" if result.plain_code != "000000" else "111111"

        with self.assertRaises(ValidationError):
            confirm_password_reset(
                phone_number="+989121234567",
                plain_code=invalid_code,
                new_password="NewStrongPassword123!",
            )

        result.challenge.refresh_from_db()

        self.assertEqual(result.challenge.attempts_count, 1)
        self.assertIsNone(result.challenge.used_at)

    def test_rejects_expired_challenge(self):
        User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        result = create_password_reset_challenge(
            phone_number="+989121234567",
        )
        result.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        result.challenge.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            confirm_password_reset(
                phone_number="+989121234567",
                plain_code=result.plain_code,
                new_password="NewStrongPassword123!",
            )

    def test_rejects_challenge_without_remaining_attempts(self):
        User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        result = create_password_reset_challenge(
            phone_number="+989121234567",
        )
        result.challenge.attempts_count = 5
        result.challenge.max_attempts = 5
        result.challenge.save(update_fields=["attempts_count", "max_attempts"])

        with self.assertRaises(ValidationError):
            confirm_password_reset(
                phone_number="+989121234567",
                plain_code=result.plain_code,
                new_password="NewStrongPassword123!",
            )

    def test_rejects_when_no_active_challenge_exists(self):
        User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            confirm_password_reset(
                phone_number="+989121234567",
                plain_code="123456",
                new_password="NewStrongPassword123!",
            )
