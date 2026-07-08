import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .managers import UserManager


iranian_phone_validator = RegexValidator(
    regex=r"^\+989\d{9}$",
    message=(
        "Phone number must be an Iranian mobile number in E.164 format. "
        "Example: +989121234567"
    ),
)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone_number = models.CharField(
        max_length=13,
        unique=True,
        null=True,
        blank=True,
        validators=[iranian_phone_validator],
    )

    email = models.EmailField(
        null=True,
        blank=True,
    )

    full_name = models.CharField(
        max_length=150,
        blank=True,
    )

    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(phone_number__isnull=True)
                    | ~Q(phone_number="")
                ),
                name="accounts_user_phone_number_not_blank",
            ),
            models.CheckConstraint(
                condition=(
                    Q(email__isnull=True)
                    | ~Q(email="")
                ),
                name="accounts_user_email_not_blank",
            ),
            models.CheckConstraint(
                condition=(
                    Q(phone_number__isnull=False)
                    | Q(email__isnull=False)
                ),
                name="accounts_user_requires_contact_method",
            ),
            models.UniqueConstraint(
                Lower("email"),
                condition=Q(email__isnull=False),
                name="accounts_user_email_case_insensitive_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.phone_number or self.email or str(self.id)

    def get_full_name(self) -> str:
        return self.full_name.strip()

    def get_short_name(self) -> str:
        if self.full_name.strip():
            return self.full_name.strip().split(" ", maxsplit=1)[0]

        return self.phone_number or self.email or ""