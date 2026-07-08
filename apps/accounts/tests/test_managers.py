from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase


User = get_user_model()


class UserManagerTests(TestCase):
    def test_creates_phone_only_user_with_unusable_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
        )

        self.assertEqual(user.phone_number, "+989121234567")
        self.assertIsNone(user.email)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_phone_verified)
        self.assertFalse(user.is_email_verified)

    def test_normalizes_email_and_blank_phone_number(self):
        user = User.objects.create_user(
            phone_number="   ",
            email="Ali@Example.COM",
        )

        self.assertIsNone(user.phone_number)
        self.assertEqual(user.email, "ali@example.com")

    def test_rejects_user_without_phone_or_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user()

    def test_normalizes_phone_number_before_creating_user(self):
        user = User.objects.create_user(
            phone_number="09121234567",
        )

        self.assertEqual(user.phone_number, "+989121234567")

    def test_rejects_invalid_iranian_phone_number(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                phone_number="02112345678",
            )

    def test_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user(
            email="ali@example.com",
        )

        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email="ALI@example.com",
            )

    def test_rejects_privileged_flags_for_regular_user(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                phone_number="+989121234567",
                is_superuser=True,
            )

    def test_creates_superuser_with_required_flags(self):
        user = User.objects.create_superuser(
            phone_number="+989121234567",
            email="admin@example.com",
            password="StrongPassword123!",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_phone_verified)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(user.check_password("StrongPassword123!"))