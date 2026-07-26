from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.services.passwords import (
    change_password_for_user,
    set_initial_password_for_user,
)
from apps.accounts.services.tokens import (
    issue_auth_token_pair,
    refresh_auth_token_pair,
)


User = get_user_model()


class PasswordServiceTests(TestCase):
    def test_sets_initial_password_for_user_without_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        self.assertFalse(user.has_usable_password())
        token_pair = issue_auth_token_pair(user)

        updated_user = set_initial_password_for_user(
            user=user,
            password="StrongPassword123!",
        )

        self.assertTrue(updated_user.check_password("StrongPassword123!"))

        with self.assertRaises(ValidationError):
            refresh_auth_token_pair(token_pair.refresh)

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

    def test_changes_password_for_user_with_existing_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)

        updated_user = change_password_for_user(
            user=user,
            current_password="OldStrongPassword123!",
            new_password="NewStrongPassword123!",
        )

        self.assertTrue(updated_user.check_password("NewStrongPassword123!"))
        self.assertFalse(updated_user.check_password("OldStrongPassword123!"))

        with self.assertRaises(ValidationError):
            refresh_auth_token_pair(token_pair.refresh)

    def test_rejects_change_password_with_wrong_current_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            change_password_for_user(
                user=user,
                current_password="WrongPassword123!",
                new_password="NewStrongPassword123!",
            )

    def test_rejects_change_password_when_password_is_not_set(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            change_password_for_user(
                user=user,
                current_password="OldStrongPassword123!",
                new_password="NewStrongPassword123!",
            )

    def test_rejects_blank_current_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            change_password_for_user(
                user=user,
                current_password="",
                new_password="NewStrongPassword123!",
            )

    def test_rejects_blank_new_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

        with self.assertRaises(ValidationError):
            change_password_for_user(
                user=user,
                current_password="OldStrongPassword123!",
                new_password="",
            )
