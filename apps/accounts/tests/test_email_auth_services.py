from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.services.email_auth import authenticate_with_email_and_password


User = get_user_model()


class EmailAuthServiceTests(TestCase):
    def test_authenticates_verified_user_with_email_and_password(self):
        user = User.objects.create_user(
            email="Ali@Example.COM",
            password="StrongPassword123!",
            is_email_verified=True,
        )

        authenticated_user = authenticate_with_email_and_password(
            email="ali@example.com",
            password="StrongPassword123!",
        )

        self.assertEqual(authenticated_user.id, user.id)

    def test_authenticates_email_case_insensitively(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )

        authenticated_user = authenticate_with_email_and_password(
            email="ALI@EXAMPLE.COM",
            password="StrongPassword123!",
        )

        self.assertEqual(authenticated_user.id, user.id)

    def test_rejects_unknown_email(self):
        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="missing@example.com",
                password="StrongPassword123!",
            )

    def test_rejects_wrong_password(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )

        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="ali@example.com",
                password="WrongPassword123!",
            )

    def test_rejects_unverified_email(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=False,
        )

        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="ali@example.com",
                password="StrongPassword123!",
            )

    def test_rejects_account_without_usable_password(self):
        User.objects.create_user(
            email="ali@example.com",
            is_email_verified=True,
        )

        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="ali@example.com",
                password="StrongPassword123!",
            )

    def test_rejects_inactive_user(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
            is_active=False,
        )

        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="ali@example.com",
                password="StrongPassword123!",
            )

    def test_rejects_blank_email(self):
        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="   ",
                password="StrongPassword123!",
            )

    def test_rejects_blank_password(self):
        with self.assertRaises(ValidationError):
            authenticate_with_email_and_password(
                email="ali@example.com",
                password="",
            )