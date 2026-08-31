from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import CardLabel, Label
from apps.collaboration.services.labels import (
    attach_label_to_card,
    create_label,
    delete_label,
    detach_label_from_card,
    update_label,
)
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class LabelServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="+989121234760",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Main Board",
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

        self.other_board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Other Board",
        )

    def test_create_label(self):
        label = create_label(
            board=self.board,
            name="  Backend  ",
            color="  green  ",
        )

        self.assertEqual(
            label.name,
            "Backend",
        )

        self.assertEqual(
            label.color,
            "green",
        )

    def test_update_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        label = update_label(
            label=label,
            name="  API  ",
            color="  blue  ",
        )

        self.assertEqual(
            label.name,
            "API",
        )

        self.assertEqual(
            label.color,
            "blue",
        )

    def test_delete_label(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        label_id = label.id

        delete_label(
            label=label,
        )

        self.assertFalse(
            Label.objects.filter(
                pk=label_id,
            ).exists()
        )

    def test_attach_label_to_card(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        card_label = attach_label_to_card(
            card=self.card,
            label=label,
        )

        self.assertTrue(
            CardLabel.objects.filter(
                pk=card_label.pk,
            ).exists()
        )

    def test_label_from_other_board_cannot_be_attached(self):
        label = create_label(
            board=self.other_board,
            name="Other",
            color="red",
        )

        with self.assertRaises(
            ValidationError
        ):
            attach_label_to_card(
                card=self.card,
                label=label,
            )

    def test_duplicate_label_attachment_is_rejected(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        attach_label_to_card(
            card=self.card,
            label=label,
        )

        with self.assertRaises(
            ValidationError
        ):
            attach_label_to_card(
                card=self.card,
                label=label,
            )

    def test_detach_label_from_card(self):
        label = create_label(
            board=self.board,
            name="Backend",
            color="green",
        )

        attach_label_to_card(
            card=self.card,
            label=label,
        )

        detach_label_from_card(
            card=self.card,
            label=label,
        )

        self.assertFalse(
            CardLabel.objects.filter(
                card=self.card,
                label=label,
            ).exists()
        )