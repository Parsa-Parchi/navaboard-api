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
from apps.collaboration.models import (
    Checklist,
    ChecklistItem,
)
from apps.collaboration.services.checklists import (
    create_checklist,
    create_checklist_item,
)
from apps.workspaces.services.memberships import (
    add_workspace_member,
)
from apps.workspaces.services.workspaces import (
    create_workspace,
)


User = get_user_model()


class ChecklistAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234790",
        )

        self.member = User.objects.create_user(
            phone_number="+989121234791",
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234792",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Workspace",
        )

        member_membership = add_workspace_member(
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
            workspace_membership=member_membership,
            role=BoardMembership.Role.MEMBER,
        )

        self.board_list = create_board_list(
            board=self.board,
            title="Todo",
        )

        self.card = create_card(
            board_list=self.board_list,
            creator=self.owner,
            title="Card",
        )

        self.list_url = reverse(
            "collaboration-api:checklist-list",
            kwargs={
                "card_id": self.card.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def test_member_can_create_and_list_checklist(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url,
            data={
                "title": "Implementation",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["title"],
            "Implementation",
        )

    def test_workspace_member_cannot_discover_private_card(self):
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

    def test_member_can_update_checklist(self):
        checklist = create_checklist(
            card=self.card,
            title="Old",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-detail",
            kwargs={
                "checklist_id": checklist.id,
            },
        )

        response = self.client.patch(
            url,
            data={
                "title": "New",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["title"],
            "New",
        )

    def test_member_can_move_checklist(self):
        first = create_checklist(
            card=self.card,
            title="First",
        )

        second = create_checklist(
            card=self.card,
            title="Second",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-move",
            kwargs={
                "checklist_id": second.id,
            },
        )

        response = self.client.post(
            url,
            data={
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(second.position, 0)
        self.assertEqual(first.position, 1)

    def test_member_can_delete_checklist(self):
        checklist = create_checklist(
            card=self.card,
            title="Delete",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-detail",
            kwargs={
                "checklist_id": checklist.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Checklist.objects.filter(
                pk=checklist.id,
            ).exists()
        )

    def test_member_can_create_item(self):
        checklist = create_checklist(
            card=self.card,
            title="Implementation",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-item-create",
            kwargs={
                "checklist_id": checklist.id,
            },
        )

        response = self.client.post(
            url,
            data={
                "title": "Create API",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertFalse(
            response.data["is_completed"],
        )

    def test_member_can_complete_item(self):
        checklist = create_checklist(
            card=self.card,
            title="Implementation",
        )

        item = create_checklist_item(
            checklist=checklist,
            title="Create API",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-item-detail",
            kwargs={
                "item_id": item.id,
            },
        )

        response = self.client.patch(
            url,
            data={
                "is_completed": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            response.data["is_completed"],
        )

    def test_member_can_move_item(self):
        checklist = create_checklist(
            card=self.card,
            title="Implementation",
        )

        first = create_checklist_item(
            checklist=checklist,
            title="First",
        )

        second = create_checklist_item(
            checklist=checklist,
            title="Second",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-item-move",
            kwargs={
                "item_id": second.id,
            },
        )

        response = self.client.post(
            url,
            data={
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(second.position, 0)
        self.assertEqual(first.position, 1)

    def test_member_can_delete_item(self):
        checklist = create_checklist(
            card=self.card,
            title="Implementation",
        )

        item = create_checklist_item(
            checklist=checklist,
            title="Delete",
        )

        self.authenticate(self.member)

        url = reverse(
            "collaboration-api:checklist-item-detail",
            kwargs={
                "item_id": item.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            ChecklistItem.objects.filter(
                pk=item.id,
            ).exists()
        )