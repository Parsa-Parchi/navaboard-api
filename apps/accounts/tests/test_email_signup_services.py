from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmailSignupChallenge
from apps.accounts.services.email_signup import (
    confirm_email_signup,
    create_email_signup_challenge,
)
from apps.accounts.services.otp import check_otp_code


User = get_user_model()


class EmailSignupServiceTests(TestCase):
    def test_request_stores_pending_data_without_creating_user(self):
        result = create_email_signup_challenge(
            email="  Ali@Example.COM  ",
            password="StrongPassword123!",
            full_name="  Ali Test  ",
            requested_ip="127.0.0.1",
        )

        challenge = result.challenge

        self.assertFalse(User.objects.exists())
        self.assertEqual(challenge.email, "ali@example.com")
        self.assertEqual(challenge.full_name, "Ali Test")
        self.assertEqual(challenge.requested_ip, "127.0.0.1")
        self.assertTrue(
            check_password("StrongPassword123!", challenge.password_hash)
        )
        self.assertTrue(check_otp_code(result.plain_code, challenge.code_hash))

    def test_confirm_creates_verified_user_and_clears_pending_password(self):
        result = create_email_signup_challenge(
            email="ali@example.com",
            password="StrongPassword123!",
            full_name="Ali Test",
        )

        confirm_result = confirm_email_signup(
            email="ALI@example.com",
            plain_code=result.plain_code,
        )

        result.challenge.refresh_from_db()
        user = confirm_result.user

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.email, "ali@example.com")
        self.assertEqual(user.full_name, "Ali Test")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(user.check_password("StrongPassword123!"))
        self.assertIsNotNone(result.challenge.used_at)
        self.assertEqual(result.challenge.password_hash, "")

    def test_reissue_revokes_old_challenge_and_replaces_pending_data(self):
        first_result = create_email_signup_challenge(
            email="ali@example.com",
            password="FirstStrongPassword123!",
            full_name="First Name",
        )
        second_result = create_email_signup_challenge(
            email="ALI@example.com",
            password="SecondStrongPassword123!",
            full_name="Second Name",
        )

        first_result.challenge.refresh_from_db()

        self.assertIsNotNone(first_result.challenge.revoked_at)
        self.assertEqual(first_result.challenge.password_hash, "")
        self.assertIsNone(second_result.challenge.revoked_at)
        self.assertTrue(
            check_password(
                "SecondStrongPassword123!",
                second_result.challenge.password_hash,
            )
        )

        confirm_result = confirm_email_signup(
            email="ali@example.com",
            plain_code=second_result.plain_code,
        )

        self.assertEqual(confirm_result.user.full_name, "Second Name")
        self.assertTrue(
            confirm_result.user.check_password("SecondStrongPassword123!")
        )

    def test_request_does_not_reactivate_or_modify_inactive_user(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="OriginalStrongPassword123!",
            full_name="Original Name",
            is_email_verified=False,
            is_active=False,
        )

        with self.assertRaises(ValidationError):
            create_email_signup_challenge(
                email="ali@example.com",
                password="AttackerStrongPassword123!",
                full_name="Attacker Name",
            )

        user.refresh_from_db()

        self.assertFalse(user.is_active)
        self.assertEqual(user.full_name, "Original Name")
        self.assertTrue(user.check_password("OriginalStrongPassword123!"))
        self.assertFalse(EmailSignupChallenge.objects.exists())

    def test_request_does_not_modify_existing_unverified_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            email="ali@example.com",
            password="OriginalStrongPassword123!",
            full_name="Original Name",
            is_phone_verified=True,
            is_email_verified=False,
        )

        with self.assertRaises(ValidationError):
            create_email_signup_challenge(
                email="ali@example.com",
                password="AttackerStrongPassword123!",
                full_name="Attacker Name",
            )

        user.refresh_from_db()

        self.assertEqual(user.full_name, "Original Name")
        self.assertTrue(user.check_password("OriginalStrongPassword123!"))
        self.assertFalse(EmailSignupChallenge.objects.exists())

    def test_invalid_code_does_not_create_user(self):
        result = create_email_signup_challenge(
            email="ali@example.com",
            password="StrongPassword123!",
        )
        invalid_code = "000000" if result.plain_code != "000000" else "111111"

        with self.assertRaises(ValidationError):
            confirm_email_signup(
                email="ali@example.com",
                plain_code=invalid_code,
            )

        result.challenge.refresh_from_db()

        self.assertFalse(User.objects.exists())
        self.assertEqual(result.challenge.attempts_count, 1)
        self.assertIsNone(result.challenge.used_at)

    def test_expired_code_does_not_create_user(self):
        result = create_email_signup_challenge(
            email="ali@example.com",
            password="StrongPassword123!",
        )
        result.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        result.challenge.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            confirm_email_signup(
                email="ali@example.com",
                plain_code=result.plain_code,
            )

        self.assertFalse(User.objects.exists())

    def test_confirm_rejects_email_registered_after_request(self):
        result = create_email_signup_challenge(
            email="ali@example.com",
            password="StrongPassword123!",
        )
        existing_user = User.objects.create_user(
            email="ali@example.com",
            password="ExistingStrongPassword123!",
            is_email_verified=True,
        )

        with self.assertRaises(ValidationError):
            confirm_email_signup(
                email="ali@example.com",
                plain_code=result.plain_code,
            )

        result.challenge.refresh_from_db()
        existing_user.refresh_from_db()

        self.assertEqual(User.objects.count(), 1)
        self.assertIsNone(result.challenge.used_at)
        self.assertNotEqual(result.challenge.password_hash, "")
        self.assertTrue(
            existing_user.check_password("ExistingStrongPassword123!")
        )
