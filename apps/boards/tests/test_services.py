from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.boards.models import (
    BoardMembership,
    BoardList,
    Card,
)
from apps.boards.services.boards import (
    add_board_member,
    change_board_member_role,
    create_board,
    remove_board_member,
    delete_board,
)
from apps.boards.services.cards import create_card, delete_card, move_card
from apps.boards.services.lists import (
    create_board_list,
    delete_board_list,
    move_board_list,
)
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.member = User.objects.create_user(phone_number="+989121234568")
        self.outsider = User.objects.create_user(phone_number="+989121234569")
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        self.member_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.member,
        )

    def test_creates_board_and_admin_membership_atomically(self):
        board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="  Product Roadmap  ",
            visibility="workspace",
        )

        membership = board.memberships.get()
        self.assertEqual(board.name, "Product Roadmap")
        self.assertEqual(board.visibility, "workspace")
        self.assertEqual(membership.user, self.owner)
        self.assertEqual(membership.role, BoardMembership.Role.ADMIN)

    def test_rejects_creator_outside_workspace(self):
        with self.assertRaises(ValidationError):
            create_board(
                workspace=self.workspace,
                creator=self.outsider,
                name="Unauthorized",
            )

    def test_adds_changes_and_removes_board_member(self):
        board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Product Roadmap",
        )

        membership = add_board_member(
            board=board,
            workspace_membership=self.member_workspace_membership,
        )
        self.assertEqual(membership.role, BoardMembership.Role.MEMBER)

        membership = change_board_member_role(
            membership=membership,
            role=BoardMembership.Role.ADMIN,
        )
        self.assertEqual(membership.role, BoardMembership.Role.ADMIN)

        remove_board_member(membership=membership)
        self.assertFalse(BoardMembership.objects.filter(pk=membership.pk).exists())

    def test_rejects_board_member_from_another_workspace(self):
        other_workspace = create_workspace(
            creator=self.outsider,
            name="Other Team",
        )
        other_membership = other_workspace.memberships.get(user=self.outsider)
        board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Product Roadmap",
        )

        with self.assertRaises(ValidationError):
            add_board_member(
                board=board,
                workspace_membership=other_membership,
            )

    def test_deletes_board_with_soft_delete_cascade(self):
        board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Delete Test Board",
        )

        board_list = create_board_list(
            board=board,
            title="Todo",
        )

        card = create_card(
            board_list=board_list,
            creator=self.owner,
            title="Test Card",
        )

        delete_board(
            board=board,
        )

        board.refresh_from_db()
        board_list.refresh_from_db()
        card.refresh_from_db()

        self.assertIsNotNone(board.deleted_at)
        self.assertIsNotNone(board_list.deleted_at)
        self.assertIsNotNone(card.deleted_at)


class BoardListServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        workspace = create_workspace(creator=self.owner, name="Product Team")
        self.board = create_board(
            workspace=workspace,
            creator=self.owner,
            name="Product Roadmap",
        )

    def titles_and_positions(self):
        return list(self.board.lists.values_list("title", "position"))

    def test_appends_and_inserts_lists(self):
        create_board_list(board=self.board, title="Todo")
        create_board_list(board=self.board, title="Done")

        create_board_list(board=self.board, title="Doing", position=1)

        self.assertEqual(
            self.titles_and_positions(),
            [("Todo", 0), ("Doing", 1), ("Done", 2)],
        )

    def test_moves_list_and_resequences_positions(self):
        todo = create_board_list(board=self.board, title="Todo")
        create_board_list(board=self.board, title="Doing")
        done = create_board_list(board=self.board, title="Done")

        move_board_list(board_list=done, position=0)

        self.assertEqual(
            self.titles_and_positions(),
            [("Done", 0), ("Todo", 1), ("Doing", 2)],
        )
        todo.refresh_from_db()
        self.assertEqual(todo.position, 1)

    def test_deletes_list_and_closes_position_gap(self):
        create_board_list(board=self.board, title="Todo")
        doing = create_board_list(board=self.board, title="Doing")
        create_board_list(board=self.board, title="Done")

        delete_board_list(board_list=doing)

        self.assertEqual(
            self.titles_and_positions(),
            [("Todo", 0), ("Done", 1)],
        )

    def test_rejects_position_outside_valid_range(self):
        create_board_list(board=self.board, title="Todo")

        with self.assertRaises(ValidationError):
            create_board_list(board=self.board, title="Invalid", position=2)


class CardServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.outsider = User.objects.create_user(phone_number="+989121234568")
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Product Roadmap",
        )
        self.todo = create_board_list(board=self.board, title="Todo")
        self.doing = create_board_list(board=self.board, title="Doing")

    def cards_in(self, board_list):
        return list(board_list.cards.values_list("title", "position"))

    def test_appends_and_inserts_cards(self):
        create_card(board_list=self.todo, creator=self.owner, title="First")
        create_card(board_list=self.todo, creator=self.owner, title="Third")

        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Second",
            position=1,
        )

        self.assertEqual(
            self.cards_in(self.todo),
            [("First", 0), ("Second", 1), ("Third", 2)],
        )

    def test_rejects_creator_outside_workspace(self):
        with self.assertRaises(ValidationError):
            create_card(
                board_list=self.todo,
                creator=self.outsider,
                title="Unauthorized",
            )

    def test_moves_card_within_same_list(self):
        first = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )
        create_card(board_list=self.todo, creator=self.owner, title="Second")
        create_card(board_list=self.todo, creator=self.owner, title="Third")

        move_card(card=first, destination_list=self.todo, position=2)

        self.assertEqual(
            self.cards_in(self.todo),
            [("Second", 0), ("Third", 1), ("First", 2)],
        )

    def test_moves_card_between_lists_on_same_board(self):
        first = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )
        moving = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Moving",
        )
        create_card(board_list=self.doing, creator=self.owner, title="Existing")

        moved_card = move_card(
            card=moving,
            destination_list=self.doing,
            position=0,
        )

        self.assertEqual(self.cards_in(self.todo), [("First", 0)])
        self.assertEqual(
            self.cards_in(self.doing),
            [("Moving", 0), ("Existing", 1)],
        )
        self.assertEqual(moved_card.board_list_id, self.doing.id)
        first.refresh_from_db()
        self.assertEqual(first.position, 0)

    def test_rejects_move_to_list_on_another_board(self):
        card = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )
        other_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Other Board",
        )
        other_list = create_board_list(board=other_board, title="Other")

        with self.assertRaises(ValidationError):
            move_card(card=card, destination_list=other_list, position=0)

        card.refresh_from_db()
        self.assertEqual(card.board_list, self.todo)

    def test_deletes_card_and_closes_position_gap(self):
        create_card(board_list=self.todo, creator=self.owner, title="First")
        second = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Second",
        )
        create_card(board_list=self.todo, creator=self.owner, title="Third")

        delete_card(card=second)

        self.assertEqual(
            self.cards_in(self.todo),
            [("First", 0), ("Third", 1)],
        )

