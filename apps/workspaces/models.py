import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Workspace(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="workspace_name_not_blank",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        self.description = self.description.strip()

        if not self.name:
            raise ValidationError({"name": "Workspace name is required."})

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workspace_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("joined_at",)
        indexes = [
            models.Index(
                fields=("user", "workspace"),
                name="ws_user_workspace_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "user"),
                name="ws_membership_unique_user",
            ),
            models.UniqueConstraint(
                fields=("workspace",),
                condition=Q(role="owner"),
                name="ws_one_owner",
            ),
            models.CheckConstraint(
                condition=Q(role__in=("owner", "admin", "member")),
                name="ws_membership_valid_role",
            ),
        ]

    @property
    def is_owner(self) -> bool:
        return self.role == self.Role.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role in {self.Role.OWNER, self.Role.ADMIN}

    def __str__(self) -> str:
        return f"{self.user} - {self.workspace} ({self.role})"

