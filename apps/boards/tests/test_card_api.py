from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.boards.models import (
    Board,
    BoardMembership,
    Card,
)
from apps.boards.services.boards import (
    add_board_member,
    create_board,
)
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CardAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234600",
        )

        self.editor = User.objects.create_user(
            phone_number="+989121234601",
        )

        self.viewer = User.objects.create_user(
            phone_number="+989121234602",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234603",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Product Team",
        )

        self.editor_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.editor,
            )
        )

        add_workspace_member(
            workspace=self.workspace,
            user=self.viewer,
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Product Board",
            visibility=Board.Visibility.WORKSPACE,
        )

        add_board_member(
            board=self.board,
            workspace_membership=(
                self.editor_workspace_membership
            ),
            role=BoardMembership.Role.MEMBER,
        )

        self.todo = create_board_list(
            board=self.board,
            title="Todo",
        )

        self.doing = create_board_list(
            board=self.board,
            title="Doing",
        )

        self.list_url = reverse(
            "boards-api:card-list",
            kwargs={
                "board_id": self.board.id,
                "list_id": self.todo.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def detail_url(self, card):
        return reverse(
            "boards-api:card-detail",
            kwargs={
                "board_id": self.board.id,
                "card_id": card.id,
            },
        )

    def move_url(self, card):
        return reverse(
            "boards-api:card-move",
            kwargs={
                "board_id": self.board.id,
                "card_id": card.id,
            },
        )


class CardListCreateAPIViewTests(
    CardAPITestCase
):
    def test_requires_authentication(self):
        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_workspace_member_can_view_cards(self):
        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )

        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Second",
        )

        self.authenticate(
            self.viewer,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            [
                item["title"]
                for item in response.data
            ],
            [
                "First",
                "Second",
            ],
        )

    def test_board_member_can_create_card(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "  Build API  ",
                "description": "  Create endpoints  ",
                "due_at": "2026-09-01T12:30:00Z",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["title"],
            "Build API",
        )

        self.assertEqual(
            response.data["description"],
            "Create endpoints",
        )

        self.assertEqual(
            response.data["position"],
            0,
        )

        self.assertEqual(
            response.data["created_by"],
            str(self.editor.id),
        )

        self.assertIsNotNone(
            response.data["due_at"],
        )

    def test_board_member_can_insert_card_at_position(self):
        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )

        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Third",
        )

        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "Second",
                "position": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            list(
                self.todo.cards.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("First", 0),
                ("Second", 1),
                ("Third", 2),
            ],
        )

    def test_workspace_member_without_board_membership_cannot_create_card(
        self,
    ):
        self.authenticate(
            self.viewer,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "Unauthorized",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_outsider_cannot_discover_cards(self):
        self.authenticate(
            self.outsider,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_invalid_insert_position_returns_400(self):
        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )

        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "Invalid",
                "position": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class CardDetailAPIViewTests(
    CardAPITestCase
):
    def setUp(self):
        super().setUp()

        self.first = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="First",
        )

        self.second = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Second",
        )

        self.third = create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Third",
        )

    def test_workspace_member_can_retrieve_card(self):
        self.authenticate(
            self.viewer,
        )

        response = self.client.get(
            self.detail_url(self.first),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.first.id),
        )

    def test_board_member_can_update_card(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.patch(
            self.detail_url(self.first),
            data={
                "title": "  Updated Card  ",
                "description": "  Updated description  ",
                "due_at": None,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["title"],
            "Updated Card",
        )

        self.assertEqual(
            response.data["description"],
            "Updated description",
        )

        self.assertIsNone(
            response.data["due_at"],
        )

        self.first.refresh_from_db()

        self.assertEqual(
            self.first.title,
            "Updated Card",
        )

    def test_workspace_member_cannot_update_card(self):
        self.authenticate(
            self.viewer,
        )

        response = self.client.patch(
            self.detail_url(self.first),
            data={
                "title": "Unauthorized",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_board_member_can_move_card_inside_same_list(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.first),
            data={
                "destination_list_id": str(self.todo.id),
                "position": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            list(
                self.todo.cards.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("Second", 0),
                ("Third", 1),
                ("First", 2),
            ],
        )

    def test_board_member_can_move_card_between_lists(self):
        existing = create_card(
            board_list=self.doing,
            creator=self.owner,
            title="Existing",
        )

        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.second),
            data={
                "destination_list_id": str(self.doing.id),
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            list(
                self.todo.cards.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("First", 0),
                ("Third", 1),
            ],
        )

        self.assertEqual(
            list(
                self.doing.cards.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("Second", 0),
                ("Existing", 1),
            ],
        )

        existing.refresh_from_db()

        self.assertEqual(
            existing.position,
            1,
        )

    def test_cannot_move_card_to_list_on_another_board(self):
        other_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Other Board",
        )

        other_list = create_board_list(
            board=other_board,
            title="Other",
        )

        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.first),
            data={
                "destination_list_id": str(other_list.id),
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "destination_list_id",
            response.data,
        )

    def test_invalid_move_position_returns_400(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.first),
            data={
                "destination_list_id": str(self.todo.id),
                "position": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_board_member_can_delete_card_and_close_gap(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.delete(
            self.detail_url(self.second),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Card.objects.filter(
                pk=self.second.id,
            ).exists()
        )

        self.assertEqual(
            list(
                self.todo.cards.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("First", 0),
                ("Third", 1),
            ],
        )

    def test_workspace_member_cannot_delete_card(self):
        self.authenticate(
            self.viewer,
        )

        response = self.client.delete(
            self.detail_url(self.first),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            Card.objects.filter(
                pk=self.first.id,
            ).exists()
        )