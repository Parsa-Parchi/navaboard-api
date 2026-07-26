from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import (
    EmailSignupChallenge,
    EmailVerificationChallenge,
)
from apps.accounts.services.email_verification import (
    EMAIL_VERIFICATION_CODE_LIFETIME,
)
from apps.accounts.services.otp import hash_otp_code


User = get_user_model()
MIGRATION_MODULE = import_module(
    "apps.accounts.migrations.0005_add_email_signup_challenge"
)


class PendingEmailSignupMigrationTests(TestCase):
    def test_moves_active_legacy_signup_out_of_user_table(self):
        user = User.objects.create_user(
            email="Ali@Example.COM",
            password="StrongPassword123!",
            full_name="Ali Test",
            is_email_verified=False,
            is_active=True,
        )
        challenge = EmailVerificationChallenge.objects.create(
            user=user,
            email="ali@example.com",
            code_hash=hash_otp_code("123456"),
            expires_at=timezone.now() + EMAIL_VERIFICATION_CODE_LIFETIME,
            requested_ip="127.0.0.1",
        )

        MIGRATION_MODULE.migrate_pending_email_signups(apps, None)

        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(
            EmailVerificationChallenge.objects.filter(pk=challenge.pk).exists()
        )

        signup_challenge = EmailSignupChallenge.objects.get(
            email="ali@example.com",
        )

        self.assertEqual(signup_challenge.full_name, "Ali Test")
        self.assertEqual(signup_challenge.code_hash, challenge.code_hash)
        self.assertEqual(signup_challenge.requested_ip, "127.0.0.1")
        self.assertTrue(
            check_password(
                "StrongPassword123!",
                signup_challenge.password_hash,
            )
        )

    def test_does_not_move_inactive_existing_account(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=False,
            is_active=False,
        )
        EmailVerificationChallenge.objects.create(
            user=user,
            email="ali@example.com",
            code_hash=hash_otp_code("123456"),
            expires_at=timezone.now() + EMAIL_VERIFICATION_CODE_LIFETIME,
        )

        MIGRATION_MODULE.migrate_pending_email_signups(apps, None)

        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(EmailSignupChallenge.objects.exists())
