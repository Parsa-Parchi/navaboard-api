from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.boards.models import Board, BoardList, BoardMembership, Card
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.workspace = create_workspace(creator=self.owner, name="Product Team")

    def test_cleans_name_and_description(self):
        board = Board(
            workspace=self.workspace,
            name="  Product Roadmap  ",
            description="  Quarterly work  ",
            created_by=self.owner,
        )

        board.full_clean()

        self.assertEqual(board.name, "Product Roadmap")
        self.assertEqual(board.description, "Quarterly work")

    def test_rejects_blank_name(self):
        board = Board(
            workspace=self.workspace,
            name="   ",
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            board.full_clean()

    def test_rejects_unknown_visibility(self):
        board = Board(
            workspace=self.workspace,
            name="Product Roadmap",
            visibility="unknown",
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            board.full_clean()


class BoardMembershipModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.member = User.objects.create_user(phone_number="+989121234568")
        self.other_owner = User.objects.create_user(phone_number="+989121234569")
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        self.other_workspace = create_workspace(
            creator=self.other_owner,
            name="Other Team",
        )
        self.member_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.member,
        )
        self.board = Board.objects.create(
            workspace=self.workspace,
            name="Product Roadmap",
            created_by=self.owner,
        )

    def test_rejects_member_from_another_workspace(self):
        other_membership = self.other_workspace.memberships.get(user=self.other_owner)
        membership = BoardMembership(
            board=self.board,
            workspace_membership=other_membership,
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_rejects_duplicate_board_membership(self):
        BoardMembership.objects.create(
            board=self.board,
            workspace_membership=self.member_workspace_membership,
        )
        duplicate = BoardMembership(
            board=self.board,
            workspace_membership=self.member_workspace_membership,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_board_membership_is_removed_with_workspace_membership(self):
        board_membership = BoardMembership.objects.create(
            board=self.board,
            workspace_membership=self.member_workspace_membership,
        )

        self.member_workspace_membership.delete()

        self.assertFalse(
            BoardMembership.objects.filter(pk=board_membership.pk).exists()
        )


class BoardContentModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        workspace = create_workspace(creator=self.owner, name="Product Team")
        self.board = Board.objects.create(
            workspace=workspace,
            name="Product Roadmap",
            created_by=self.owner,
        )
        self.board_list = BoardList.objects.create(
            board=self.board,
            title="Todo",
            position=0,
        )

    def test_rejects_blank_list_title(self):
        board_list = BoardList(board=self.board, title="   ", position=1)

        with self.assertRaises(ValidationError):
            board_list.full_clean()

    def test_database_rejects_duplicate_list_position(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BoardList.objects.create(
                board=self.board,
                title="Duplicate",
                position=0,
            )

    def test_cleans_card_title_and_description(self):
        card = Card(
            board_list=self.board_list,
            title="  Implement API  ",
            description="  Add endpoints  ",
            position=0,
            created_by=self.owner,
        )

        card.full_clean()

        self.assertEqual(card.title, "Implement API")
        self.assertEqual(card.description, "Add endpoints")

    def test_rejects_blank_card_title(self):
        card = Card(
            board_list=self.board_list,
            title="   ",
            position=0,
            created_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            card.full_clean()

    def test_database_rejects_duplicate_card_position(self):
        Card.objects.create(
            board_list=self.board_list,
            title="First",
            position=0,
            created_by=self.owner,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Card.objects.create(
                board_list=self.board_list,
                title="Duplicate",
                position=0,
                created_by=self.owner,
            )

