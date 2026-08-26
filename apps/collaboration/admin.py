from django.contrib import admin

# Register your models here.
from django.contrib import admin

from apps.collaboration.models import (
    CardAssignee,
    CardLabel,
    Checklist,
    ChecklistItem,
    Comment,
    Label,
)


@admin.register(CardAssignee)
class CardAssigneeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "card",
        "workspace_membership",
        "assigned_by",
        "assigned_at",
    )

    search_fields = (
        "card__title",
        "workspace_membership__user__phone_number",
        "assigned_by__phone_number",
    )

    list_select_related = (
        "card",
        "workspace_membership__user",
        "assigned_by",
    )

    readonly_fields = (
        "assigned_at",
    )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "card",
        "author",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "body",
        "card__title",
        "author__phone_number",
    )

    list_select_related = (
        "card",
        "author",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "color",
        "board",
        "created_at",
    )

    search_fields = (
        "name",
        "board__name",
    )

    list_select_related = (
        "board",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(CardLabel)
class CardLabelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "card",
        "label",
    )

    search_fields = (
        "card__title",
        "label__name",
    )

    list_select_related = (
        "card",
        "label",
    )


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "card",
        "position",
        "created_at",
    )

    search_fields = (
        "title",
        "card__title",
    )

    list_select_related = (
        "card",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "checklist",
        "position",
        "is_completed",
        "created_at",
    )

    list_filter = (
        "is_completed",
    )

    search_fields = (
        "title",
        "checklist__title",
        "checklist__card__title",
    )

    list_select_related = (
        "checklist__card",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )