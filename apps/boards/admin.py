from django.contrib import admin

from .models import Board, BoardList, BoardMembership, Card


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "workspace",
        "visibility",
        "created_by",
        "created_at",
    )
    list_filter = ("visibility", "created_at")
    search_fields = (
        "id",
        "name",
        "workspace__name",
        "created_by__phone_number",
        "created_by__email",
    )
    list_select_related = ("workspace", "created_by")
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "workspace",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BoardMembership)
class BoardMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "board",
        "workspace_member",
        "role",
        "joined_at",
    )
    list_filter = ("role", "joined_at")
    search_fields = (
        "id",
        "board__name",
        "workspace_membership__user__phone_number",
        "workspace_membership__user__email",
    )
    list_select_related = (
        "board",
        "workspace_membership__user",
    )
    readonly_fields = (
        "id",
        "board",
        "workspace_membership",
        "role",
        "joined_at",
    )

    @admin.display(description="User")
    def workspace_member(self, obj):
        return obj.user

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BoardList)
class BoardListAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "board", "position", "created_at")
    search_fields = ("id", "title", "board__name")
    list_select_related = ("board",)
    ordering = ("board", "position")
    readonly_fields = (
        "id",
        "board",
        "position",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "board_list",
        "position",
        "due_at",
        "created_by",
        "created_at",
    )
    list_filter = ("due_at", "created_at")
    search_fields = (
        "id",
        "title",
        "board_list__title",
        "board_list__board__name",
    )
    list_select_related = ("board_list__board", "created_by")
    ordering = ("board_list", "position")
    readonly_fields = (
        "id",
        "board_list",
        "position",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

