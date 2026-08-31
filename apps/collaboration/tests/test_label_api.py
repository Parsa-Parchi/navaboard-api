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
from apps.collaboration.models import CardLabel, Label
from apps.collaboration.services.labels import (
    attach_label_to_card,
    create_label,
)
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class LabelAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234770",
        )

        self.admin = User.objects.create_user(
            phone_number="+989121234771",
        )

        self.member = User.objects.create_user(
            phone_number="+989121234772",
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234773",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
        )

        self.admin_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.admin,
        )

        self.member_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.member,
        )

        add_workspace_member(
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
            workspace_membership=self.admin_membership,
            role=BoardMembership.Role.ADMIN,
        )

        add_board_member(
            board=self.board,
            workspace_membership=self.member_membership,
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

        self.board_labels_url = reverse(
            "collaboration-api:board-label-list",
            kwargs={
                "board_id": self.board.id,
            },
        )

        self.card_labels_url = reverse(
            "collaboration-api:card-label-create",
            kwargs={
                "card_id": self.card.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def board_label_detail_url(self, label):
        return reverse(
            "collaboration-api:board-label-detail",
            kwargs={
                "board_id": self.board.id,
                "label_id": label.id,
            },
        )

    def card_label_detail_url(self, label):
        return reverse(
            "collaboration-api:card-label-detail",
            kwargs={
                "card_id": self.card.id,
                "label_id": label.id,
            },
        )


class BoardLabelAPITests(LabelAPITestCase):
    def test_board_member_can_list_labels(self):
        create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.member,
        )

        response = self.client.get(
            self.board_labels_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["name"],
            "Backend",
        )

    def test_workspace_member_cannot_discover_private_board(self):
        self.authenticate(
            self.workspace_member,
        )

        response = self.client.get(
            self.board_labels_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_board_admin_can_create_label(self):
        self.authenticate(
            self.admin,
        )

        response = self.client.post(
            self.board_labels_url,
            data={
                "name": "Backend",
                "color": "green",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_board_member_cannot_create_label(self):
        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.board_labels_url,
            data={
                "name": "Backend",
                "color": "green",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_board_admin_can_update_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.admin,
        )

        response = self.client.patch(
            self.board_label_detail_url(label),
            data={
                "name": "API",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["name"],
            "API",
        )

    def test_board_member_cannot_update_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.member,
        )

        response = self.client.patch(
            self.board_label_detail_url(label),
            data={
                "name": "API",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_board_admin_can_delete_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.admin,
        )

        response = self.client.delete(
            self.board_label_detail_url(label),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )


class CardLabelAPITests(LabelAPITestCase):
    def test_board_member_can_attach_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.card_labels_url,
            data={
                "label_id": str(label.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["label"]["id"],
            str(label.id),
        )

    def test_duplicate_attachment_is_rejected(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        attach_label_to_card(
            card=self.card,
            label=label,
        )

        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.card_labels_url,
            data={
                "label_id": str(label.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_label_from_other_board_is_rejected(self):
        other_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Other Board",
        )

        label = create_label(
            board=other_board,
            name="Other",
            color="red",
        )

        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.card_labels_url,
            data={
                "label_id": str(label.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_board_member_can_detach_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        attach_label_to_card(
            card=self.card,
            label=label,
        )

        self.authenticate(
            self.member,
        )

        response = self.client.delete(
            self.card_label_detail_url(label),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            CardLabel.objects.filter(
                card=self.card,
                label=label,
            ).exists()
        )

    def test_workspace_member_cannot_attach_to_private_card(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        self.authenticate(
            self.workspace_member,
        )

        response = self.client.post(
            self.card_labels_url,
            data={
                "label_id": str(label.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )