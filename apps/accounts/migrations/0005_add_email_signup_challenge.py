import uuid

from django.contrib.auth.hashers import is_password_usable
from django.db import migrations, models
from django.db.models.functions import Lower
from django.utils import timezone


def migrate_pending_email_signups(apps, schema_editor):
    user_model = apps.get_model("accounts", "User")
    email_verification = apps.get_model(
        "accounts",
        "EmailVerificationChallenge",
    )
    email_signup = apps.get_model("accounts", "EmailSignupChallenge")
    now = timezone.now()

    pending_users = user_model.objects.filter(
        phone_number__isnull=True,
        email__isnull=False,
        is_email_verified=False,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    ).exclude(email="")

    for user in pending_users.iterator():
        challenge = (
            email_verification.objects.filter(
                user_id=user.pk,
                email__iexact=user.email,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if challenge is None or not is_password_usable(user.password):
            continue

        challenge_is_expired = challenge.expires_at <= now
        signup_challenge = email_signup.objects.create(
            email=user.email.strip().lower(),
            full_name=user.full_name,
            password_hash="" if challenge_is_expired else user.password,
            code_hash=challenge.code_hash,
            expires_at=challenge.expires_at,
            attempts_count=challenge.attempts_count,
            max_attempts=challenge.max_attempts,
            used_at=challenge.used_at,
            revoked_at=now if challenge_is_expired else challenge.revoked_at,
            requested_ip=challenge.requested_ip,
        )
        email_signup.objects.filter(pk=signup_challenge.pk).update(
            created_at=challenge.created_at,
        )
        user.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_bind_phone_change_challenge_to_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailSignupChallenge",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("full_name", models.CharField(blank=True, max_length=150)),
                ("password_hash", models.CharField(blank=True, max_length=255)),
                ("code_hash", models.CharField(max_length=255)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempts_count", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_ip",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["email", "created_at"],
                        name="email_signup_email_created_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(email=""),
                        name="email_signup_email_not_blank",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(code_hash=""),
                        name="email_signup_code_not_blank",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(max_attempts__gte=1),
                        name="email_signup_attempts_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            attempts_count__lte=models.F("max_attempts"),
                        ),
                        name="email_signup_attempts_lte_max",
                    ),
                    models.CheckConstraint(
                        condition=(
                            ~models.Q(password_hash="")
                            | models.Q(used_at__isnull=False)
                            | models.Q(revoked_at__isnull=False)
                        ),
                        name="email_signup_active_has_pwd",
                    ),
                    models.UniqueConstraint(
                        Lower("email"),
                        condition=models.Q(
                            used_at__isnull=True,
                            revoked_at__isnull=True,
                        ),
                        name="email_signup_one_active",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            migrate_pending_email_signups,
            migrations.RunPython.noop,
        ),
    ]
