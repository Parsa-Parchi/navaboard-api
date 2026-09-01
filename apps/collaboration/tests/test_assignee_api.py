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
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import CardAssignee
from apps.collaboration.services.assignees import add_card_assignee
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CardAssigneeAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234730",
            full_name="Owner",
        )

        self.board_admin = User.objects.create_user(
            phone_number="+989121234731",
            full_name="Board Admin",
        )

        self.board_member = User.objects.create_user(
            phone_number="+989121234732",
            full_name="Board Member",
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234733",
            full_name="Workspace Member",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234734",
            full_name="Outsider",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
        )

        self.admin_workspace_membership = add_workspace_member(
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

        add_board_member(
            board=self.board,
            workspace_membership=self.admin_workspace_membership,
            role=BoardMembership.Role.ADMIN,
        )

        add_board_member(
            board=self.board,
            workspace_membership=(
                self.board_member_workspace_membership
            ),
            role=BoardMembership.Role.MEMBER,
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

        self.list_url = reverse(
            "collaboration-api:card-assignee-list",
            kwargs={
                "card_id": self.card.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def detail_url(self, assignee):
        return reverse(
            "collaboration-api:card-assignee-detail",
            kwargs={
                "card_id": self.card.id,
                "assignee_id": assignee.id,
            },
        )


class CardAssigneeListCreateAPITests(
    CardAssigneeAPITestCase
):
    def test_requires_authentication(self):
        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_board_member_can_list_assignees(self):
        add_card_assignee(
            card=self.card,
            workspace_membership=(
                self.workspace_member_membership
            ),
            assigned_by=self.owner,
        )

        self.authenticate(
            self.board_member,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["user"]["id"],
            str(self.workspace_member.id),
        )

    def test_workspace_member_cannot_discover_private_card(
        self,
    ):
        self.authenticate(
            self.workspace_member,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_board_admin_can_assign_workspace_member(self):
        self.authenticate(
            self.board_admin,
        )

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.workspace_member.phone_number,
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

    def test_board_member_cannot_assign_user(self):
        self.authenticate(
            self.board_member,
        )

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.workspace_member.phone_number,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_assign_user_outside_workspace(self):
        self.authenticate(
            self.board_admin,
        )

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.outsider.phone_number,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "phone_number",
            response.data,
        )

    def test_duplicate_assignee_is_rejected(self):
        add_card_assignee(
            card=self.card,
            workspace_membership=(
                self.workspace_member_membership
            ),
            assigned_by=self.owner,
        )

        self.authenticate(
            self.board_admin,
        )

        response = self.client.post(
            self.list_url,
            data={
                "phone_number": self.workspace_member.phone_number,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class CardAssigneeDetailAPITests(
    CardAssigneeAPITestCase
):
    def setUp(self):
        super().setUp()

        self.assignee = add_card_assignee(
            card=self.card,
            workspace_membership=(
                self.workspace_member_membership
            ),
            assigned_by=self.owner,
        )

    def test_board_admin_can_remove_assignee(self):
        self.authenticate(
            self.board_admin,
        )

        assignee_id = self.assignee.id

        response = self.client.delete(
            self.detail_url(self.assignee),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            CardAssignee.objects.filter(
                pk=assignee_id,
            ).exists()
        )

    def test_board_member_cannot_remove_assignee(self):
        self.authenticate(
            self.board_member,
        )

        response = self.client.delete(
            self.detail_url(self.assignee),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )