import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def revoke_unowned_phone_change_challenges(apps, schema_editor):
    otp_challenge = apps.get_model("accounts", "OTPChallenge")
    otp_challenge.objects.filter(
        purpose="change_phone",
        used_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_add_email_verification_challenge_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="otpchallenge",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="requested_otp_challenges",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            revoke_unowned_phone_change_challenges,
            migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="otpchallenge",
            index=models.Index(
                fields=[
                    "requested_by",
                    "phone_number",
                    "purpose",
                    "created_at",
                ],
                name="otp_req_phone_purpose_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="otpchallenge",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(purpose="change_phone")
                    | models.Q(requested_by__isnull=False)
                    | models.Q(used_at__isnull=False)
                    | models.Q(revoked_at__isnull=False)
                ),
                name="otp_change_active_has_user",
            ),
        ),
    ]
