from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.services.labels import create_label, attach_label_to_card
from apps.workspaces.services.workspaces import create_workspace
from apps.workspaces.services.memberships import add_workspace_member


class CardLabelReadTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(phone_number="09121111001")
        self.viewer = get_user_model().objects.create_user(phone_number="09121111002")
        self.workspace = create_workspace(creator=self.owner, name="W")
        add_workspace_member(workspace=self.workspace, user=self.viewer)
        self.board = create_board(workspace=self.workspace, creator=self.owner, name="B", visibility="workspace")
        self.card = create_card(board_list=create_board_list(board=self.board, title="L"), creator=self.owner, title="C")
        self.label = create_label(board=self.board, name="Urgent", color="#ff0000")
        self.link = attach_label_to_card(card=self.card, label=self.label)
        self.url = f"/api/cards/{self.card.pk}/labels/"
        self.client.force_authenticate(self.viewer)

    def test_reader_can_restore_attached_label_state(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["id"]), str(self.link.pk))
        self.assertEqual(str(response.data[0]["label"]["id"]), str(self.label.pk))
        self.assertEqual(response.data[0]["label"]["name"], "Urgent")

    def test_deleted_label_is_excluded(self):
        self.label.delete()
        self.assertEqual(self.client.get(self.url).data, [])

    def test_private_board_is_inaccessible_to_workspace_reader(self):
        self.board.visibility = "private"
        self.board.save(update_fields=["visibility"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_deleted_parent_is_inaccessible(self):
        self.card.board_list.delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)
