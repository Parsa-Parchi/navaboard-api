import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q , F
from django.db.models.functions import Lower

from .managers import UserManager
from django.utils import timezone

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


class OTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        VERIFY_PHONE = "verify_phone", "Verify phone"
        CHANGE_PHONE = "change_phone", "Change phone"
        PASSWORD_RESET = "password_reset", "Password reset"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone_number = models.CharField(
        max_length=13,
        validators=[iranian_phone_validator],
        db_index=True,
    )

    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        default=Purpose.LOGIN,
    )

    code_hash = models.CharField(
        max_length=255,
    )

    expires_at = models.DateTimeField(
        db_index=True,
    )

    attempts_count = models.PositiveSmallIntegerField(
        default=0,
    )

    max_attempts = models.PositiveSmallIntegerField(
        default=5,
    )

    used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    requested_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["phone_number", "purpose", "created_at"],
                name="otp_phone_purpose_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(phone_number=""),
                name="otp_phone_not_blank",
            ),
            models.CheckConstraint(
                condition=~Q(code_hash=""),
                name="otp_code_hash_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="otp_max_attempts_positive",
            ),
            models.CheckConstraint(
                condition=Q(attempts_count__lte=F("max_attempts")),
                name="otp_attempts_lte_max",
            ),
        ]


    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def has_attempts_remaining(self) -> bool:
        return self.attempts_count < self.max_attempts

    @property
    def can_be_verified(self) -> bool:
        return (
            not self.is_expired
            and not self.is_used
            and not self.is_revoked
            and self.has_attempts_remaining
        )


    def __str__(self) -> str:
        return f"{self.phone_number} - {self.purpose}"

class EmailVerificationChallenge(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_challenges",
    )

    email = models.EmailField(
        db_index=True,
    )

    code_hash = models.CharField(
        max_length=255,
    )

    expires_at = models.DateTimeField(
        db_index=True,
    )

    attempts_count = models.PositiveSmallIntegerField(
        default=0,
    )

    max_attempts = models.PositiveSmallIntegerField(
        default=5,
    )

    used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    requested_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "email", "created_at"],
                name="email_verify_user_email_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(email=""),
                name="email_verify_email_not_blank",
            ),
            models.CheckConstraint(
                condition=~Q(code_hash=""),
                name="email_verify_code_hash_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="email_verify_max_attempts_positive",
            ),
            models.CheckConstraint(
                condition=Q(attempts_count__lte=F("max_attempts")),
                name="email_verify_attempts_lte_max",
            ),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def has_attempts_remaining(self) -> bool:
        return self.attempts_count < self.max_attempts

    @property
    def can_be_verified(self) -> bool:
        return (
            not self.is_expired
            and not self.is_used
            and not self.is_revoked
            and self.has_attempts_remaining
        )

    def __str__(self) -> str:
        return f"{self.email} - {self.user_id}"