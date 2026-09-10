import uuid

from django.conf import settings
from django.db import models


class Activity(models.Model):
    """Immutable API mutation history; never stores request bodies or credentials."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE)
    board = models.ForeignKey("boards.Board", null=True, on_delete=models.CASCADE)
    card = models.ForeignKey("boards.Card", null=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    resource_id = models.CharField(max_length=36, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "-created_at")), models.Index(fields=("board", "-created_at"))]


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="notifications")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [models.UniqueConstraint(fields=("recipient", "activity"), name="notification_unique_recipient_event")]
        indexes = [models.Index(fields=("recipient", "read_at", "-created_at"))]
