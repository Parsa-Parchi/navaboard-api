import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.workspaces.models import Workspace, WorkspaceMembership


from apps.core.models import SoftDeleteModel


class Board(SoftDeleteModel):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        WORKSPACE = "workspace", "Workspace"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="boards",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_boards",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("workspace", "visibility", "created_at"),
                name="board_ws_visibility_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="board_name_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=("private", "workspace")),
                name="board_valid_visibility",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        self.description = self.description.strip()

        if not self.name:
            raise ValidationError({"name": "Board name is required."})

    def __str__(self) -> str:
        return self.name


class BoardMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    workspace_membership = models.ForeignKey(
        WorkspaceMembership,
        on_delete=models.CASCADE,
        related_name="board_memberships",
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
                fields=("workspace_membership", "board"),
                name="board_member_ws_board_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("board", "workspace_membership"),
                name="board_membership_unique_user",
            ),
            models.CheckConstraint(
                condition=Q(role__in=("admin", "member")),
                name="board_membership_valid_role",
            ),
        ]

    @property
    def user(self):
        return self.workspace_membership.user

    @property
    def user_id(self):
        return self.workspace_membership.user_id

    def clean(self) -> None:
        super().clean()
        if (
            self.board_id
            and self.workspace_membership_id
            and self.board.workspace_id != self.workspace_membership.workspace_id
        ):
            raise ValidationError(
                {
                    "workspace_membership": (
                        "Board members must belong to the board's workspace."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.user} - {self.board} ({self.role})"


class BoardList(SoftDeleteModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name="lists",
    )
    title = models.CharField(max_length=120)
    position = models.PositiveIntegerField()


    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""),
                name="board_list_title_not_blank",
            ),
            models.UniqueConstraint(
                fields=("board", "position"),
                condition=Q(deleted_at__isnull=True),
                name="board_list_unique_position",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.title = self.title.strip()
        if not self.title:
            raise ValidationError({"title": "List title is required."})

    def __str__(self) -> str:
        return f"{self.board} - {self.title}"


class Card(SoftDeleteModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    board_list = models.ForeignKey(
        BoardList,
        on_delete=models.CASCADE,
        related_name="cards",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField()
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_cards",
    )


    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""),
                name="card_title_not_blank",
            ),
            models.UniqueConstraint(
                fields=("board_list", "position"),
                condition=Q(deleted_at__isnull=True),
                name="card_unique_list_position",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title:
            raise ValidationError({"title": "Card title is required."})

    def __str__(self) -> str:
        return self.title

