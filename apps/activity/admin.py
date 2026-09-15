from django.contrib import admin

from apps.activity.models import Activity, Notification


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "workspace", "board", "card", "created_at")
    list_filter = ("action", "created_at")
    search_fields = (
        "action",
        "actor__phone_number",
        "workspace__name",
        "board__name",
        "card__title",
    )
    list_select_related = ("actor", "workspace", "board", "card")
    readonly_fields = (
        "id",
        "workspace",
        "board",
        "card",
        "actor",
        "action",
        "resource_id",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "activity", "read_at", "created_at")
    list_filter = ("read_at", "created_at")
    search_fields = ("recipient__phone_number", "activity__action")
    list_select_related = ("recipient", "activity")
    readonly_fields = ("id", "recipient", "activity", "created_at")

    def has_add_permission(self, request):
        return False
