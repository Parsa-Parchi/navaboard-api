from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.boards.models import (
    Board,
    BoardMembership,
)
from apps.boards.services.boards import (
    add_board_member,
    create_board,
)
from apps.workspaces.services.memberships import (
    add_workspace_member,
)
from apps.workspaces.services.workspaces import (
    create_workspace,
)


User = get_user_model()


class BoardAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234567"
        )

        self.member = User.objects.create_user(
            phone_number="+989121234568"
        )

        self.board_member = User.objects.create_user(
            phone_number="+989121234569"
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234570"
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Product Team",
        )

        self.member_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.member,
            )
        )

        self.board_member_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.board_member,
            )
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user
        )


class BoardListCreateAPIViewTests(
    BoardAPITestCase
):
    def setUp(self):
        super().setUp()

        self.url = reverse(
            "boards-api:board-list",
            kwargs={
                "workspace_id": self.workspace.id,
            },
        )

    def test_requires_authentication(self):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_workspace_member_can_create_board(self):
        self.authenticate(
            self.member
        )

        response = self.client.post(
            self.url,
            data={
                "name": "  Sprint Board  ",
                "description": "  Backend work  ",
                "visibility": "private",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["name"],
            "Sprint Board",
        )

        self.assertEqual(
            response.data["description"],
            "Backend work",
        )

        self.assertEqual(
            response.data["visibility"],
            "private",
        )

        self.assertEqual(
            response.data["current_user_role"],
            "admin",
        )

        board = Board.objects.get(
            pk=response.data["id"]
        )

        self.assertTrue(
            board.memberships.filter(
                workspace_membership__user=(
                    self.member
                ),
                role=BoardMembership.Role.ADMIN,
            ).exists()
        )

    def test_outsider_cannot_create_board_in_workspace(
        self,
    ):
        self.authenticate(
            self.outsider
        )

        response = self.client.post(
            self.url,
            data={
                "name": "Unauthorized Board",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_workspace_member_lists_only_visible_boards(
        self,
    ):
        workspace_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Workspace Board",
            visibility=Board.Visibility.WORKSPACE,
        )

        private_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Private Board",
            visibility=Board.Visibility.PRIVATE,
        )

        self.authenticate(
            self.member
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            str(workspace_board.id),
            returned_ids,
        )

        self.assertNotIn(
            str(private_board.id),
            returned_ids,
        )

    def test_board_member_can_list_private_board(
        self,
    ):
        private_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Private Board",
            visibility=Board.Visibility.PRIVATE,
        )

        add_board_member(
            board=private_board,
            workspace_membership=(
                self.board_member_workspace_membership
            ),
            role=BoardMembership.Role.MEMBER,
        )

        self.authenticate(
            self.board_member
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            str(private_board.id),
            returned_ids,
        )


class BoardDetailAPIViewTests(
    BoardAPITestCase
):
    def setUp(self):
        super().setUp()

        self.private_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Private Board",
            visibility=Board.Visibility.PRIVATE,
        )

        add_board_member(
            board=self.private_board,
            workspace_membership=(
                self.board_member_workspace_membership
            ),
            role=BoardMembership.Role.MEMBER,
        )

        self.url = reverse(
            "boards-api:board-detail",
            kwargs={
                "board_id": self.private_board.id,
            },
        )

    def test_requires_authentication(self):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_board_member_can_retrieve_private_board(
        self,
    ):
        self.authenticate(
            self.board_member
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.private_board.id),
        )

        self.assertEqual(
            response.data["current_user_role"],
            "member",
        )

    def test_workspace_member_cannot_discover_private_board(
        self,
    ):
        self.authenticate(
            self.member
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_board_member_cannot_update_board_settings(
        self,
    ):
        self.authenticate(
            self.board_member
        )

        response = self.client.patch(
            self.url,
            data={
                "name": "Unauthorized Name",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.private_board.refresh_from_db()

        self.assertEqual(
            self.private_board.name,
            "Private Board",
        )

    def test_board_admin_can_update_board(
        self,
    ):
        self.authenticate(
            self.owner
        )

        response = self.client.patch(
            self.url,
            data={
                "name": "  Updated Board  ",
                "description": (
                    "  Updated description  "
                ),
                "visibility": "workspace",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["name"],
            "Updated Board",
        )

        self.assertEqual(
            response.data["description"],
            "Updated description",
        )

        self.assertEqual(
            response.data["visibility"],
            "workspace",
        )

    def test_workspace_owner_has_admin_override(
        self,
    ):
        board_created_by_member = create_board(
            workspace=self.workspace,
            creator=self.member,
            name="Member Board",
            visibility=Board.Visibility.PRIVATE,
        )

        self.assertFalse(
            board_created_by_member.memberships.filter(
                workspace_membership__user=(
                    self.owner
                ),
            ).exists()
        )

        url = reverse(
            "boards-api:board-detail",
            kwargs={
                "board_id": (
                    board_created_by_member.id
                ),
            },
        )

        self.authenticate(
            self.owner
        )

        response = self.client.patch(
            url,
            data={
                "name": "Owner Managed Board",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["name"],
            "Owner Managed Board",
        )

        self.assertEqual(
            response.data["current_user_role"],
            "admin",
        )

    def test_board_member_cannot_delete_board(
        self,
    ):
        self.authenticate(
            self.board_member
        )

        response = self.client.delete(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            Board.objects.filter(
                pk=self.private_board.pk
            ).exists()
        )

    def test_board_admin_can_delete_board(
        self,
    ):
        self.authenticate(
            self.owner
        )

        response = self.client.delete(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Board.objects.filter(
                pk=self.private_board.pk
            ).exists()
        )