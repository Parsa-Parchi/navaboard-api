from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import EmailVerificationChallenge, OTPChallenge, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "id",
        "phone_number",
        "email",
        "full_name",
        "is_phone_verified",
        "is_email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_phone_verified",
        "is_email_verified",
        "created_at",
    )
    search_fields = (
        "id",
        "phone_number",
        "email",
        "full_name",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "phone_number",
                    "email",
                    "full_name",
                    "password",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "is_phone_verified",
                    "is_email_verified",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_phone_verified",
                    "is_email_verified",
                ),
            },
        ),
    )


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "phone_number",
        "purpose",
        "expires_at",
        "attempts_count",
        "max_attempts",
        "used_at",
        "revoked_at",
        "created_at",
    )
    list_filter = (
        "purpose",
        "created_at",
        "expires_at",
        "used_at",
        "revoked_at",
    )
    search_fields = (
        "id",
        "phone_number",
        "requested_ip",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "phone_number",
        "purpose",
        "code_hash",
        "expires_at",
        "attempts_count",
        "max_attempts",
        "used_at",
        "revoked_at",
        "requested_ip",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EmailVerificationChallenge)
class EmailVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "email",
        "expires_at",
        "attempts_count",
        "max_attempts",
        "used_at",
        "revoked_at",
        "created_at",
    )
    list_filter = (
        "created_at",
        "expires_at",
        "used_at",
        "revoked_at",
    )
    search_fields = (
        "id",
        "email",
        "user__phone_number",
        "user__email",
        "requested_ip",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "user",
        "email",
        "code_hash",
        "expires_at",
        "attempts_count",
        "max_attempts",
        "used_at",
        "revoked_at",
        "requested_ip",
        "created_at",
    )

    def has_add_permission(self, request):
        return False