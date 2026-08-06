from django.contrib import admin

from .models import Workspace, WorkspaceMembership


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "created_by",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "id",
        "name",
        "created_by__phone_number",
        "created_by__email",
    )
    list_select_related = ("created_by",)
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "workspace",
        "user",
        "role",
        "joined_at",
    )
    list_filter = ("role", "joined_at")
    search_fields = (
        "id",
        "workspace__name",
        "user__phone_number",
        "user__email",
    )
    list_select_related = ("workspace", "user")
    ordering = ("-joined_at",)
    readonly_fields = (
        "id",
        "workspace",
        "user",
        "role",
        "joined_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

