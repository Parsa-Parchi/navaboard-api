from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import (
    CardAssignee,
    CardLabel,
    Checklist,
    ChecklistItem,
    Comment,
    Label,
)
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CollaborationModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="+989121234700",
        )

        self.member = User.objects.create_user(
            phone_number="+989121234701",
        )

        self.other_user = User.objects.create_user(
            phone_number="+989121234702",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
        )

        self.owner_workspace_membership = (
            WorkspaceMembership.objects.get(
                workspace=self.workspace,
                user=self.owner,
            )
        )

        self.member_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.member,
            )
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Main Board",
        )

        self.board_list = create_board_list(
            board=self.board,
            title="Todo",
        )

        self.card = create_card(
            board_list=self.board_list,
            creator=self.owner,
            title="Main Card",
        )

        self.other_workspace = create_workspace(
            creator=self.other_user,
            name="Other Workspace",
        )

        self.other_workspace_membership = (
            WorkspaceMembership.objects.get(
                workspace=self.other_workspace,
                user=self.other_user,
            )
        )

        self.other_board = create_board(
            workspace=self.other_workspace,
            creator=self.other_user,
            name="Other Board",
        )

        self.other_list = create_board_list(
            board=self.other_board,
            title="Other List",
        )

        self.other_card = create_card(
            board_list=self.other_list,
            creator=self.other_user,
            title="Other Card",
        )

    def test_card_assignee_can_be_created(self):
        assignee = CardAssignee(
            card=self.card,
            workspace_membership=(
                self.member_workspace_membership
            ),
            assigned_by=self.owner,
        )

        assignee.full_clean()
        assignee.save()

        self.assertEqual(
            assignee.user,
            self.member,
        )

        self.assertEqual(
            assignee.user_id,
            self.member.id,
        )

    def test_card_assignee_must_belong_to_card_workspace(
        self,
    ):
        assignee = CardAssignee(
            card=self.card,
            workspace_membership=(
                self.other_workspace_membership
            ),
            assigned_by=self.owner,
        )

        with self.assertRaises(
            ValidationError
        ):
            assignee.full_clean()

    def test_card_assignee_cannot_be_duplicated(self):
        CardAssignee.objects.create(
            card=self.card,
            workspace_membership=(
                self.member_workspace_membership
            ),
            assigned_by=self.owner,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                CardAssignee.objects.create(
                    card=self.card,
                    workspace_membership=(
                        self.member_workspace_membership
                    ),
                    assigned_by=self.owner,
                )

    def test_comment_body_is_trimmed(self):
        comment = Comment(
            card=self.card,
            author=self.owner,
            body="  Backend API is ready.  ",
        )

        comment.full_clean()
        comment.save()

        self.assertEqual(
            comment.body,
            "Backend API is ready.",
        )

    def test_comment_body_cannot_be_blank(self):
        comment = Comment(
            card=self.card,
            author=self.owner,
            body="   ",
        )

        with self.assertRaises(
            ValidationError
        ):
            comment.full_clean()

    def test_label_fields_are_trimmed(self):
        label = Label(
            board=self.board,
            name="  Backend  ",
            color="  green  ",
        )

        label.full_clean()
        label.save()

        self.assertEqual(
            label.name,
            "Backend",
        )

        self.assertEqual(
            label.color,
            "green",
        )

    def test_label_name_cannot_be_blank(self):
        label = Label(
            board=self.board,
            name="   ",
            color="green",
        )

        with self.assertRaises(
            ValidationError
        ):
            label.full_clean()

    def test_card_label_can_be_created(self):
        label = Label.objects.create(
            board=self.board,
            name="Backend",
            color="green",
        )

        card_label = CardLabel(
            card=self.card,
            label=label,
        )

        card_label.full_clean()
        card_label.save()

        self.assertEqual(
            card_label.card,
            self.card,
        )

        self.assertEqual(
            card_label.label,
            label,
        )

    def test_card_label_must_belong_to_same_board(self):
        other_label = Label.objects.create(
            board=self.other_board,
            name="Other",
            color="blue",
        )

        card_label = CardLabel(
            card=self.card,
            label=other_label,
        )

        with self.assertRaises(
            ValidationError
        ):
            card_label.full_clean()

    def test_card_label_cannot_be_duplicated(self):
        label = Label.objects.create(
            board=self.board,
            name="Backend",
            color="green",
        )

        CardLabel.objects.create(
            card=self.card,
            label=label,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                CardLabel.objects.create(
                    card=self.card,
                    label=label,
                )

    def test_checklist_title_is_trimmed(self):
        checklist = Checklist(
            card=self.card,
            title="  Implementation  ",
            position=0,
        )

        checklist.full_clean()
        checklist.save()

        self.assertEqual(
            checklist.title,
            "Implementation",
        )

    def test_checklist_title_cannot_be_blank(self):
        checklist = Checklist(
            card=self.card,
            title="   ",
            position=0,
        )

        with self.assertRaises(
            ValidationError
        ):
            checklist.full_clean()

    def test_checklist_position_must_be_unique_per_card(
        self,
    ):
        Checklist.objects.create(
            card=self.card,
            title="First",
            position=0,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                Checklist.objects.create(
                    card=self.card,
                    title="Second",
                    position=0,
                )

    def test_checklist_item_can_be_created(self):
        checklist = Checklist.objects.create(
            card=self.card,
            title="Implementation",
            position=0,
        )

        item = ChecklistItem(
            checklist=checklist,
            title="Create API",
            position=0,
        )

        item.full_clean()
        item.save()

        self.assertFalse(
            item.is_completed,
        )

        item.is_completed = True
        item.save()

        item.refresh_from_db()

        self.assertTrue(
            item.is_completed,
        )

    def test_checklist_item_title_cannot_be_blank(
        self,
    ):
        checklist = Checklist.objects.create(
            card=self.card,
            title="Implementation",
            position=0,
        )

        item = ChecklistItem(
            checklist=checklist,
            title="   ",
            position=0,
        )

        with self.assertRaises(
            ValidationError
        ):
            item.full_clean()

    def test_checklist_item_position_must_be_unique(
        self,
    ):
        checklist = Checklist.objects.create(
            card=self.card,
            title="Implementation",
            position=0,
        )

        ChecklistItem.objects.create(
            checklist=checklist,
            title="First",
            position=0,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                ChecklistItem.objects.create(
                    checklist=checklist,
                    title="Second",
                    position=0,
                )

    def test_deleting_card_cascades_collaboration_data(
        self,
    ):
        CardAssignee.objects.create(
            card=self.card,
            workspace_membership=(
                self.member_workspace_membership
            ),
            assigned_by=self.owner,
        )

        Comment.objects.create(
            card=self.card,
            author=self.owner,
            body="Test comment",
        )

        label = Label.objects.create(
            board=self.board,
            name="Backend",
            color="green",
        )

        CardLabel.objects.create(
            card=self.card,
            label=label,
        )

        checklist = Checklist.objects.create(
            card=self.card,
            title="Implementation",
            position=0,
        )

        ChecklistItem.objects.create(
            checklist=checklist,
            title="Create API",
            position=0,
        )

        self.card.delete()

        self.assertEqual(
            CardAssignee.objects.count(),
            0,
        )

        self.assertEqual(
            Comment.objects.count(),
            0,
        )

        self.assertEqual(
            CardLabel.objects.count(),
            0,
        )

        self.assertEqual(
            Checklist.objects.count(),
            0,
        )

        self.assertEqual(
            ChecklistItem.objects.count(),
            0,
        )

        self.assertTrue(
            Label.objects.filter(
                pk=label.pk,
            ).exists()
        )