from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import (
    Checklist,
    ChecklistItem,
)
from apps.collaboration.services.checklists import (
    create_checklist,
    create_checklist_item,
    delete_checklist,
    delete_checklist_item,
    move_checklist,
    move_checklist_item,
    update_checklist,
    update_checklist_item,
)
from apps.workspaces.services.workspaces import (
    create_workspace,
)


User = get_user_model()


class ChecklistServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="+989121234780",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Workspace",
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Board",
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

    def test_checklists_are_appended(self):
        first = create_checklist(
            card=self.card,
            title="First",
        )

        second = create_checklist(
            card=self.card,
            title="Second",
        )

        self.assertEqual(first.position, 0)
        self.assertEqual(second.position, 1)

    def test_update_checklist(self):
        checklist = create_checklist(
            card=self.card,
            title="Old",
        )

        checklist = update_checklist(
            checklist=checklist,
            title="  New  ",
        )

        self.assertEqual(
            checklist.title,
            "New",
        )

    def test_move_checklist(self):
        first = create_checklist(
            card=self.card,
            title="First",
        )

        second = create_checklist(
            card=self.card,
            title="Second",
        )

        third = create_checklist(
            card=self.card,
            title="Third",
        )

        move_checklist(
            checklist=third,
            position=0,
        )

        result = list(
            Checklist.objects.filter(
                card=self.card,
            ).order_by("position")
        )

        self.assertEqual(
            [obj.id for obj in result],
            [
                third.id,
                first.id,
                second.id,
            ],
        )

    def test_invalid_checklist_position_rejected(self):
        checklist = create_checklist(
            card=self.card,
            title="First",
        )

        with self.assertRaises(
            ValidationError
        ):
            move_checklist(
                checklist=checklist,
                position=3,
            )

    def test_delete_checklist_compacts_positions(self):
        first = create_checklist(
            card=self.card,
            title="First",
        )

        second = create_checklist(
            card=self.card,
            title="Second",
        )

        third = create_checklist(
            card=self.card,
            title="Third",
        )

        delete_checklist(
            checklist=second,
        )

        first.refresh_from_db()
        third.refresh_from_db()

        self.assertEqual(first.position, 0)
        self.assertEqual(third.position, 1)

    def test_items_are_appended(self):
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

        self.assertEqual(first.position, 0)
        self.assertEqual(second.position, 1)

    def test_update_item(self):
        checklist = create_checklist(
            card=self.card,
            title="Implementation",
        )

        item = create_checklist_item(
            checklist=checklist,
            title="Old",
        )

        item = update_checklist_item(
            item=item,
            title="  New  ",
            is_completed=True,
        )

        self.assertEqual(item.title, "New")
        self.assertTrue(item.is_completed)

    def test_move_item(self):
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

        third = create_checklist_item(
            checklist=checklist,
            title="Third",
        )

        move_checklist_item(
            item=third,
            position=0,
        )

        result = list(
            ChecklistItem.objects.filter(
                checklist=checklist,
            ).order_by("position")
        )

        self.assertEqual(
            [obj.id for obj in result],
            [
                third.id,
                first.id,
                second.id,
            ],
        )

    def test_delete_item_compacts_positions(self):
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

        third = create_checklist_item(
            checklist=checklist,
            title="Third",
        )

        delete_checklist_item(
            item=second,
        )

        first.refresh_from_db()
        third.refresh_from_db()

        self.assertEqual(first.position, 0)
        self.assertEqual(third.position, 1)