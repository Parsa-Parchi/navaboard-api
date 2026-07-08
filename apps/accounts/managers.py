from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import BaseUserManager

from .phone_numbers import normalize_iranian_mobile_number




class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def _normalize_phone_number(phone_number: str | None) -> str | None:
        return normalize_iranian_mobile_number(phone_number)



    def _normalize_email_address(self, email: str | None) -> str | None:
        if email is None:
            return None

        normalized_email = email.strip()
        if not normalized_email:
            return None

        return self.normalize_email(normalized_email).lower()

    def _create_user(
        self,
        phone_number: str | None,
        email: str | None,
        password: str | None,
        **extra_fields: Any,
    ):
        phone_number = self._normalize_phone_number(phone_number)
        email = self._normalize_email_address(email)

        if phone_number is None and email is None:
            raise ValueError("A phone number or email address is required.")

        user = self.model(
            phone_number=phone_number,
            email=email,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.full_clean()
        user.save(using=self._db)

        return user

    def create_user(
        self,
        phone_number: str | None = None,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        if extra_fields["is_staff"] is not False:
            raise ValueError("Regular users must have is_staff=False.")

        if extra_fields["is_superuser"] is not False:
            raise ValueError("Regular users must have is_superuser=False.")

        return self._create_user(
            phone_number=phone_number,
            email=email,
            password=password,
            **extra_fields,
        )

    def create_superuser(
        self,
        phone_number: str,
        password: str | None = None,
        **extra_fields: Any,
    ):
        phone_number = self._normalize_phone_number(phone_number)
        email = self._normalize_email_address(extra_fields.pop("email", None))

        if phone_number is None:
            raise ValueError("Superusers must have a phone number.")

        if email is None:
            raise ValueError("Superusers must have an email address.")

        if not password:
            raise ValueError("Superusers must have a password.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_phone_verified", True)
        extra_fields.setdefault("is_email_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(
            phone_number=phone_number,
            email=email,
            password=password,
            **extra_fields,
        )