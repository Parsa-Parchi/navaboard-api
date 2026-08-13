from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)
from rest_framework.views import APIView

from apps.boards.api.permissions import (
    CanEditBoard,
    CanViewBoard,
    IsBoardAdmin,
)
from apps.boards.models import Board, BoardMembership
from apps.boards.services.boards import (
    add_board_member,
    create_board,
)
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.workspaces.services.memberships import (
    add_workspace_member,
)
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.owner = User.objects.create_user(
            phone_number="+989121234567"
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234568"
        )

        self.board_member = User.objects.create_user(
            phone_number="+989121234569"
        )

        self.board_admin = User.objects.create_user(
            phone_number="+989121234570"
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234571"
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Product Team",
        )

        add_workspace_member(
            workspace=self.workspace,
            user=self.workspace_member,
        )

        board_member_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.board_member,
            )
        )

        board_admin_workspace_membership = (
            add_workspace_member(
                workspace=self.workspace,
                user=self.board_admin,
            )
        )

        self.private_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Private Board",
            visibility=Board.Visibility.PRIVATE,
        )

        self.workspace_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Workspace Board",
            visibility=Board.Visibility.WORKSPACE,
        )

        add_board_member(
            board=self.private_board,
            workspace_membership=(
                board_member_workspace_membership
            ),
            role=BoardMembership.Role.MEMBER,
        )

        add_board_member(
            board=self.private_board,
            workspace_membership=(
                board_admin_workspace_membership
            ),
            role=BoardMembership.Role.ADMIN,
        )

        self.board_list = create_board_list(
            board=self.private_board,
            title="Todo",
        )

        self.card = create_card(
            board_list=self.board_list,
            creator=self.owner,
            title="Build API",
        )

    def _request_for(self, user):
        request = self.factory.get("/")

        force_authenticate(
            request,
            user=user,
        )

        return APIView().initialize_request(request)

    def test_workspace_member_can_view_workspace_board(self):
        permission = CanViewBoard()

        result = permission.has_object_permission(
            self._request_for(self.workspace_member),
            None,
            self.workspace_board,
        )

        self.assertTrue(result)

    def test_workspace_member_cannot_view_private_board(self):
        permission = CanViewBoard()

        result = permission.has_object_permission(
            self._request_for(self.workspace_member),
            None,
            self.private_board,
        )

        self.assertFalse(result)

    def test_board_member_can_view_private_board(self):
        permission = CanViewBoard()

        result = permission.has_object_permission(
            self._request_for(self.board_member),
            None,
            self.private_board,
        )

        self.assertTrue(result)

    def test_outsider_cannot_view_workspace_board(self):
        permission = CanViewBoard()

        result = permission.has_object_permission(
            self._request_for(self.outsider),
            None,
            self.workspace_board,
        )

        self.assertFalse(result)

    def test_board_member_can_edit_board_content(self):
        permission = CanEditBoard()
        request = self._request_for(self.board_member)

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.private_board,
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.board_list,
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.card,
            )
        )

    def test_workspace_member_cannot_edit_without_membership(self):
        permission = CanEditBoard()

        result = permission.has_object_permission(
            self._request_for(self.workspace_member),
            None,
            self.workspace_board,
        )

        self.assertFalse(result)

    def test_board_admin_can_manage_board(self):
        permission = IsBoardAdmin()

        result = permission.has_object_permission(
            self._request_for(self.board_admin),
            None,
            self.private_board,
        )

        self.assertTrue(result)

    def test_board_member_cannot_manage_board(self):
        permission = IsBoardAdmin()

        result = permission.has_object_permission(
            self._request_for(self.board_member),
            None,
            self.private_board,
        )

        self.assertFalse(result)

    def test_workspace_owner_has_board_admin_override(self):
        permission = IsBoardAdmin()
        request = self._request_for(self.owner)

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.private_board,
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.board_list,
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request,
                None,
                self.card,
            )
        )