from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmailVerificationChallenge


User = get_user_model()


class EmailVerificationChallengeModelTests(TestCase):
    def _build_email_challenge(self, **overrides):
        user = overrides.pop(
            "user",
            User.objects.create_user(
                phone_number="+989121234567",
                is_phone_verified=True,
            ),
        )
        data = {
            "user": user,
            "email": "ali@example.com",
            "code_hash": "hashed-code-value",
            "expires_at": timezone.now() + timedelta(minutes=10),
        }
        data.update(overrides)
        return EmailVerificationChallenge(**data)

    def test_active_challenge_can_be_verified(self):
        challenge = self._build_email_challenge()

        self.assertFalse(challenge.is_expired)
        self.assertFalse(challenge.is_used)
        self.assertFalse(challenge.is_revoked)
        self.assertTrue(challenge.has_attempts_remaining)
        self.assertTrue(challenge.can_be_verified)

    def test_expired_challenge_cannot_be_verified(self):
        challenge = self._build_email_challenge(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(challenge.is_expired)
        self.assertFalse(challenge.can_be_verified)

    def test_used_challenge_cannot_be_verified(self):
        challenge = self._build_email_challenge(
            used_at=timezone.now(),
        )

        self.assertTrue(challenge.is_used)
        self.assertFalse(challenge.can_be_verified)

    def test_revoked_challenge_cannot_be_verified(self):
        challenge = self._build_email_challenge(
            revoked_at=timezone.now(),
        )

        self.assertTrue(challenge.is_revoked)
        self.assertFalse(challenge.can_be_verified)

    def test_challenge_without_remaining_attempts_cannot_be_verified(self):
        challenge = self._build_email_challenge(
            attempts_count=5,
            max_attempts=5,
        )

        self.assertFalse(challenge.has_attempts_remaining)
        self.assertFalse(challenge.can_be_verified)

    def test_rejects_blank_email(self):
        challenge = self._build_email_challenge(email="")

        with self.assertRaises(ValidationError):
            challenge.full_clean()

    def test_rejects_attempts_count_greater_than_max_attempts(self):
        challenge = self._build_email_challenge(
            attempts_count=6,
            max_attempts=5,
        )

        with self.assertRaises(ValidationError):
            challenge.full_clean()