from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.services.passwords import set_initial_password_for_user


User = get_user_model()


class PasswordServiceTests(TestCase):
    def test_sets_initial_password_for_user_without_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        self.assertFalse(user.has_usable_password())

        updated_user = set_initial_password_for_user(
            user=user,
            password="StrongPassword123!",
        )

        self.assertTrue(updated_user.check_password("StrongPassword123!"))

    def test_rejects_blank_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            set_initial_password_for_user(
                user=user,
                password="",
            )

    def test_rejects_when_password_is_already_set(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="StrongPassword123!",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            set_initial_password_for_user(
                user=user,
                password="AnotherStrongPassword123!",
            )

    def test_rejects_common_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            set_initial_password_for_user(
                user=user,
                password="password",
            )