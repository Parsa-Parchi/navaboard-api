import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.boards.models import Board, Card
from apps.workspaces.models import WorkspaceMembership


class CardAssignee(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="assignees",
    )
    workspace_membership = models.ForeignKey(
        WorkspaceMembership,
        on_delete=models.CASCADE,
        related_name="card_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="assigned_card_members",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("assigned_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("card", "workspace_membership"),
                name="card_assignee_unique_member",
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
            self.card_id
            and self.workspace_membership_id
            and self.card.board_list.board.workspace_id
            != self.workspace_membership.workspace_id
        ):
            raise ValidationError(
                {
                    "workspace_membership": (
                        "Card assignees must belong "
                        "to the card's workspace."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.user} - {self.card}"


class Comment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="authored_card_comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(body=""),
                name="comment_body_not_blank",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        self.body = self.body.strip()

        if not self.body:
            raise ValidationError(
                {"body": "Comment body is required."}
            )

    def __str__(self) -> str:
        return self.body[:80]


class Label(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name="labels",
    )
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="label_name_not_blank",
            ),
            models.CheckConstraint(
                condition=~Q(color=""),
                name="label_color_not_blank",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        self.name = self.name.strip()
        self.color = self.color.strip()

        if not self.name:
            raise ValidationError(
                {"name": "Label name is required."}
            )

        if not self.color:
            raise ValidationError(
                {"color": "Label color is required."}
            )

    def __str__(self) -> str:
        return f"{self.board} - {self.name}"


class CardLabel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="label_links",
    )
    label = models.ForeignKey(
        Label,
        on_delete=models.CASCADE,
        related_name="card_links",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("card", "label"),
                name="card_label_unique_pair",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        if (
            self.card_id
            and self.label_id
            and self.card.board_list.board_id
            != self.label.board_id
        ):
            raise ValidationError(
                {
                    "label": (
                        "Card labels must belong to "
                        "the same board as the card."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.card} - {self.label}"


class Checklist(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="checklists",
    )
    title = models.CharField(max_length=120)
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""),
                name="checklist_title_not_blank",
            ),
            models.UniqueConstraint(
                fields=("card", "position"),
                name="checklist_unique_card_position",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        self.title = self.title.strip()

        if not self.title:
            raise ValidationError(
                {"title": "Checklist title is required."}
            )

    def __str__(self) -> str:
        return f"{self.card} - {self.title}"


class ChecklistItem(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    title = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""),
                name="checklist_item_title_not_blank",
            ),
            models.UniqueConstraint(
                fields=("checklist", "position"),
                name="checklist_item_unique_position",
            ),
        ]

    def clean(self) -> None:
        super().clean()

        self.title = self.title.strip()

        if not self.title:
            raise ValidationError(
                {"title": "Checklist item title is required."}
            )

    def __str__(self) -> str:
        return self.title