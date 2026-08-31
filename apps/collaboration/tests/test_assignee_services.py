from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import CardAssignee
from apps.collaboration.services.assignees import (
    add_card_assignee,
    remove_card_assignee,
)
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CardAssigneeServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="+989121234720",
        )

        self.member = User.objects.create_user(
            phone_number="+989121234721",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234722",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
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
            creator=self.outsider,
            name="Other Workspace",
        )

        self.other_membership = (
            WorkspaceMembership.objects.get(
                workspace=self.other_workspace,
                user=self.outsider,
            )
        )

    def test_add_card_assignee(self):
        assignee = add_card_assignee(
            card=self.card,
            workspace_membership=(
                self.member_workspace_membership
            ),
            assigned_by=self.owner,
        )

        self.assertTrue(
            CardAssignee.objects.filter(
                pk=assignee.pk,
            ).exists()
        )

    def test_assignee_must_belong_to_same_workspace(self):
        with self.assertRaises(
            ValidationError
        ):
            add_card_assignee(
                card=self.card,
                workspace_membership=self.other_membership,
                assigned_by=self.owner,
            )

    def test_assigning_user_must_belong_to_workspace(self):
        with self.assertRaises(
            ValidationError
        ):
            add_card_assignee(
                card=self.card,
                workspace_membership=(
                    self.member_workspace_membership
                ),
                assigned_by=self.outsider,
            )

    def test_remove_card_assignee(self):
        assignee = add_card_assignee(
            card=self.card,
            workspace_membership=(
                self.member_workspace_membership
            ),
            assigned_by=self.owner,
        )

        assignee_id = assignee.id

        remove_card_assignee(
            assignee=assignee,
        )

        self.assertFalse(
            CardAssignee.objects.filter(
                pk=assignee_id,
            ).exists()
        )