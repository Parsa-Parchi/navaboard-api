from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.boards.models import (
    Board,
    BoardMembership,
    BoardList,
)
from apps.boards.services.boards import (
    add_board_member,
    create_board,
)
from apps.boards.services.lists import create_board_list
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardListAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234590",
        )

        self.editor = User.objects.create_user(
            phone_number="+989121234591",
        )

        self.viewer = User.objects.create_user(
            phone_number="+989121234592",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234593",
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

        self.list_url = reverse(
            "boards-api:list-list",
            kwargs={
                "board_id": self.board.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def detail_url(self, board_list):
        return reverse(
            "boards-api:list-detail",
            kwargs={
                "board_id": self.board.id,
                "list_id": board_list.id,
            },
        )

    def move_url(self, board_list):
        return reverse(
            "boards-api:list-move",
            kwargs={
                "board_id": self.board.id,
                "list_id": board_list.id,
            },
        )


class BoardListListCreateAPIViewTests(
    BoardListAPITestCase
):
    def test_requires_authentication(self):
        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_workspace_member_can_view_lists_of_workspace_board(
        self,
    ):
        create_board_list(
            board=self.board,
            title="Todo",
        )

        create_board_list(
            board=self.board,
            title="Doing",
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
            [item["title"] for item in response.data],
            [
                "Todo",
                "Doing",
            ],
        )

    def test_board_member_can_create_list(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "  Todo  ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["title"],
            "Todo",
        )

        self.assertEqual(
            response.data["position"],
            0,
        )

    def test_board_member_can_insert_list_at_position(self):
        create_board_list(
            board=self.board,
            title="Todo",
        )

        create_board_list(
            board=self.board,
            title="Done",
        )

        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.list_url,
            data={
                "title": "Doing",
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
                self.board.lists.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("Todo", 0),
                ("Doing", 1),
                ("Done", 2),
            ],
        )

    def test_workspace_member_without_board_membership_cannot_create_list(
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

    def test_outsider_cannot_discover_board_lists(self):
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
        create_board_list(
            board=self.board,
            title="Todo",
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


class BoardListDetailAPIViewTests(
    BoardListAPITestCase
):
    def setUp(self):
        super().setUp()

        self.todo = create_board_list(
            board=self.board,
            title="Todo",
        )

        self.doing = create_board_list(
            board=self.board,
            title="Doing",
        )

        self.done = create_board_list(
            board=self.board,
            title="Done",
        )

    def test_board_member_can_update_list_title(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.patch(
            self.detail_url(self.todo),
            data={
                "title": "  Backlog  ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["title"],
            "Backlog",
        )

        self.todo.refresh_from_db()

        self.assertEqual(
            self.todo.title,
            "Backlog",
        )

    def test_workspace_member_cannot_update_list(self):
        self.authenticate(
            self.viewer,
        )

        response = self.client.patch(
            self.detail_url(self.todo),
            data={
                "title": "Unauthorized",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_board_member_can_move_list(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.done),
            data={
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
                self.board.lists.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("Done", 0),
                ("Todo", 1),
                ("Doing", 2),
            ],
        )

    def test_invalid_move_position_returns_400(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.post(
            self.move_url(self.todo),
            data={
                "position": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_board_member_can_delete_list_and_close_gap(self):
        self.authenticate(
            self.editor,
        )

        response = self.client.delete(
            self.detail_url(self.doing),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertEqual(
            list(
                self.board.lists.values_list(
                    "title",
                    "position",
                )
            ),
            [
                ("Todo", 0),
                ("Done", 1),
            ],
        )

    def test_workspace_member_cannot_delete_list(self):
        self.authenticate(
            self.viewer,
        )

        response = self.client.delete(
            self.detail_url(self.todo),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            BoardList.objects.filter(
                pk=self.todo.pk,
            ).exists()
        )