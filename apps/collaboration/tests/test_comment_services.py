from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import Comment
from apps.collaboration.services.comments import (
    create_comment,
    delete_comment,
    update_comment,
)
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CommentServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone_number="+989121234740",
        )

        self.outsider = User.objects.create_user(
            phone_number="+989121234741",
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

    def test_create_comment(self):
        comment = create_comment(
            card=self.card,
            author=self.owner,
            body="  API is ready.  ",
        )

        self.assertEqual(
            comment.body,
            "API is ready.",
        )

        self.assertEqual(
            comment.author,
            self.owner,
        )

    def test_comment_author_must_belong_to_workspace(self):
        with self.assertRaises(
            ValidationError
        ):
            create_comment(
                card=self.card,
                author=self.outsider,
                body="Unauthorized comment",
            )

    def test_update_comment(self):
        comment = create_comment(
            card=self.card,
            author=self.owner,
            body="Initial",
        )

        comment = update_comment(
            comment=comment,
            body="  Updated  ",
        )

        self.assertEqual(
            comment.body,
            "Updated",
        )

    def test_delete_comment(self):
        comment = create_comment(
            card=self.card,
            author=self.owner,
            body="Delete me",
        )

        comment_id = comment.id

        delete_comment(
            comment=comment,
        )

        self.assertFalse(
            Comment.objects.filter(
                pk=comment_id,
            ).exists()
        )