from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import check_otp_code
from apps.accounts.services.phone_change import (
    confirm_phone_change,
    create_phone_change_challenge,
)


User = get_user_model()


class PhoneChangeServiceTests(TestCase):
    def test_creates_phone_change_challenge(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        result = create_phone_change_challenge(
            user=user,
            phone_number="0912 444 5566",
            requested_ip="127.0.0.1",
        )

        challenge = result.challenge

        self.assertEqual(challenge.phone_number, "+989124445566")
        self.assertEqual(challenge.purpose, OTPChallenge.Purpose.CHANGE_PHONE)
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertEqual(len(result.plain_code), 6)
        self.assertTrue(result.plain_code.isdigit())
        self.assertNotEqual(challenge.code_hash, result.plain_code)
        self.assertTrue(check_otp_code(result.plain_code, challenge.code_hash))

    def test_rejects_phone_number_already_used_by_another_user(self):
        User.objects.create_user(
            phone_number="+989124445566",
            is_phone_verified=True,
        )
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            create_phone_change_challenge(
                user=user,
                phone_number="+989124445566",
            )

    def test_rejects_current_verified_phone_number(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            create_phone_change_challenge(
                user=user,
                phone_number="0912 123 4567",
            )

    def test_confirms_phone_change_and_updates_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_phone_change_challenge(
            user=user,
            phone_number="+989124445566",
        )

        confirm_result = confirm_phone_change(
            user=user,
            phone_number="0912 444 5566",
            plain_code=result.plain_code,
        )

        user.refresh_from_db()
        result.challenge.refresh_from_db()

        self.assertEqual(confirm_result.user.id, user.id)
        self.assertEqual(user.phone_number, "+989124445566")
        self.assertTrue(user.is_phone_verified)
        self.assertIsNotNone(result.challenge.used_at)

    def test_rejects_invalid_code_and_increments_attempts_count(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_phone_change_challenge(
            user=user,
            phone_number="+989124445566",
        )
        invalid_code = "000000" if result.plain_code != "000000" else "111111"

        with self.assertRaises(ValidationError):
            confirm_phone_change(
                user=user,
                phone_number="+989124445566",
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
        result = create_phone_change_challenge(
            user=user,
            phone_number="+989124445566",
        )
        result.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        result.challenge.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            confirm_phone_change(
                user=user,
                phone_number="+989124445566",
                plain_code=result.plain_code,
            )

    def test_rejects_challenge_without_remaining_attempts(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        result = create_phone_change_challenge(
            user=user,
            phone_number="+989124445566",
        )
        result.challenge.attempts_count = 5
        result.challenge.max_attempts = 5
        result.challenge.save(update_fields=["attempts_count", "max_attempts"])

        with self.assertRaises(ValidationError):
            confirm_phone_change(
                user=user,
                phone_number="+989124445566",
                plain_code=result.plain_code,
            )

    def test_rejects_when_no_active_challenge_exists(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            confirm_phone_change(
                user=user,
                phone_number="+989124445566",
                plain_code="123456",
            )