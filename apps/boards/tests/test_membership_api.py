from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.boards.models import BoardMembership
from apps.boards.services.boards import (
    add_board_member,
    create_board,
)
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardMembershipAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234580",
            full_name="Workspace Owner",
        )

        self.board_admin = User.objects.create_user(
            phone_number="+989121234581",
            full_name="Board Admin",
        )

        self.board_member = User.objects.create_user(
            phone_number="+989121234582",
            full_name="Board Member",
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234583",
            full_name="Workspace Member",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234584",
            full_name="Outsider",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Product Team",
        )

        self.board_admin_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.board_admin,
        )

        self.board_member_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.board_member,
        )

        self.workspace_member_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.workspace_member,
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Private Board",
        )

        self.board_admin_membership = add_board_member(
            board=self.board,
            workspace_membership=self.board_admin_workspace_membership,
            role=BoardMembership.Role.ADMIN,
        )

        self.board_member_membership = add_board_member(
            board=self.board,
            workspace_membership=self.board_member_workspace_membership,
            role=BoardMembership.Role.MEMBER,
        )

        self.list_url = reverse(
            "boards-api:membership-list",
            kwargs={
                "board_id": self.board.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def detail_url(self, membership):
        return reverse(
            "boards-api:membership-detail",
            kwargs={
                "board_id": self.board.id,
                "membership_id": membership.id,
            },
        )


class BoardMembershipListCreateAPIViewTests(
    BoardMembershipAPITestCase
):
    def test_requires_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_board_member_can_list_board_members(self):
        self.authenticate(self.board_member)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_user_ids = {
            item["user"]["id"]
            for item in response.data
        }

        self.assertIn(
            str(self.owner.id),
            returned_user_ids,
        )

        self.assertIn(
            str(self.board_admin.id),
            returned_user_ids,
        )

        self.assertIn(
            str(self.board_member.id),
            returned_user_ids,
        )

    def test_workspace_member_cannot_discover_private_board_members(
        self,
    ):
        self.authenticate(self.workspace_member)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_board_admin_can_add_workspace_member(self):
        self.authenticate(self.board_admin)

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.workspace_member.phone_number,
                "role": BoardMembership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["user"]["id"],
            str(self.workspace_member.id),
        )

        self.assertEqual(
            response.data["role"],
            BoardMembership.Role.MEMBER,
        )

        self.assertTrue(
            BoardMembership.objects.filter(
                board=self.board,
                workspace_membership=self.workspace_member_membership,
                role=BoardMembership.Role.MEMBER,
            ).exists()
        )

    def test_regular_board_member_cannot_add_member(self):
        self.authenticate(self.board_member)

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.workspace_member.phone_number,
                "role": BoardMembership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_add_user_outside_workspace(self):
        self.authenticate(self.board_admin)

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.outsider.phone_number,
                "role": BoardMembership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "user_id",
            response.data,
        )

    def test_cannot_add_duplicate_board_member(self):
        self.authenticate(self.board_admin)

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.board_member.phone_number,
                "role": BoardMembership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class BoardMembershipDetailAPIViewTests(
    BoardMembershipAPITestCase
):
    def test_board_admin_can_change_member_role(self):
        self.authenticate(self.board_admin)

        response = self.client.patch(
            self.detail_url(self.board_member_membership),
            data={
                "role": BoardMembership.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["role"],
            BoardMembership.Role.ADMIN,
        )

        self.board_member_membership.refresh_from_db()

        self.assertEqual(
            self.board_member_membership.role,
            BoardMembership.Role.ADMIN,
        )

    def test_regular_board_member_cannot_change_role(self):
        self.authenticate(self.board_member)

        response = self.client.patch(
            self.detail_url(self.board_admin_membership),
            data={
                "role": BoardMembership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_board_admin_can_remove_other_member(self):
        self.authenticate(self.board_admin)

        membership_id = self.board_member_membership.id

        response = self.client.delete(
            self.detail_url(self.board_member_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            BoardMembership.objects.filter(
                pk=membership_id,
            ).exists()
        )

    def test_regular_board_member_can_leave_board(self):
        self.authenticate(self.board_member)

        membership_id = self.board_member_membership.id

        response = self.client.delete(
            self.detail_url(self.board_member_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            BoardMembership.objects.filter(
                pk=membership_id,
            ).exists()
        )

    def test_regular_board_member_cannot_remove_other_member(
        self,
    ):
        self.authenticate(self.board_member)

        response = self.client.delete(
            self.detail_url(self.board_admin_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_workspace_member_cannot_access_private_membership_detail(
        self,
    ):
        self.authenticate(self.workspace_member)

        response = self.client.patch(
            self.detail_url(self.board_member_membership),
            data={
                "role": BoardMembership.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )