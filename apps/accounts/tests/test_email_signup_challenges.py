from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmailSignupChallenge


class EmailSignupChallengeModelTests(TestCase):
    def _build_challenge(self, **overrides):
        data = {
            "email": "ali@example.com",
            "full_name": "Ali Test",
            "password_hash": "hashed-password-value",
            "code_hash": "hashed-code-value",
            "expires_at": timezone.now() + timedelta(minutes=10),
        }
        data.update(overrides)
        return EmailSignupChallenge(**data)

    def test_active_challenge_can_be_verified(self):
        challenge = self._build_challenge()

        self.assertTrue(challenge.can_be_verified)

    def test_expired_challenge_cannot_be_verified(self):
        challenge = self._build_challenge(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertFalse(challenge.can_be_verified)

    def test_active_challenge_requires_password_hash(self):
        challenge = self._build_challenge(password_hash="")

        with self.assertRaises(ValidationError):
            challenge.full_clean()

    def test_used_challenge_can_clear_password_hash(self):
        challenge = self._build_challenge(
            password_hash="",
            used_at=timezone.now(),
        )

        challenge.full_clean()

    def test_rejects_attempts_count_greater_than_max_attempts(self):
        challenge = self._build_challenge(
            attempts_count=6,
            max_attempts=5,
        )

        with self.assertRaises(ValidationError):
            challenge.full_clean()

    def test_allows_only_one_active_challenge_per_email(self):
        EmailSignupChallenge.objects.create(
            email="ali@example.com",
            password_hash="first-password-hash",
            code_hash="first-code-hash",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EmailSignupChallenge.objects.create(
                    email="ALI@example.com",
                    password_hash="second-password-hash",
                    code_hash="second-code-hash",
                    expires_at=timezone.now() + timedelta(minutes=10),
                )
