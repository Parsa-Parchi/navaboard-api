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
from apps.collaboration.models import Comment
from apps.collaboration.services.comments import create_comment
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class CommentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234750",
        )

        self.member = User.objects.create_user(
            phone_number="+989121234751",
        )

        self.other_member = User.objects.create_user(
            phone_number="+989121234752",
        )

        self.workspace_member = User.objects.create_user(
            phone_number="+989121234753",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Main Workspace",
        )

        self.member_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.member,
        )

        self.other_member_workspace_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.other_member,
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
            workspace_membership=self.member_workspace_membership,
            role=BoardMembership.Role.MEMBER,
        )

        add_board_member(
            board=self.board,
            workspace_membership=self.other_member_workspace_membership,
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
            "collaboration-api:comment-list",
            kwargs={
                "card_id": self.card.id,
            },
        )

    def authenticate(self, user):
        self.client.force_authenticate(
            user=user,
        )

    def detail_url(self, comment):
        return reverse(
            "collaboration-api:comment-detail",
            kwargs={
                "comment_id": comment.id,
            },
        )


class CommentListCreateAPITests(
    CommentAPITestCase
):
    def test_requires_authentication(self):
        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_board_member_can_list_comments(self):
        create_comment(
            card=self.card,
            author=self.owner,
            body="First comment",
        )

        self.authenticate(
            self.member,
        )

        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["body"],
            "First comment",
        )

    def test_board_member_can_create_comment(self):
        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.list_url,
            data={
                "body": "  My comment  ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["body"],
            "My comment",
        )

        self.assertEqual(
            response.data["author"]["id"],
            str(self.member.id),
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

    def test_blank_comment_is_rejected(self):
        self.authenticate(
            self.member,
        )

        response = self.client.post(
            self.list_url,
            data={
                "body": "   ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class CommentDetailAPITests(
    CommentAPITestCase
):
    def setUp(self):
        super().setUp()

        self.comment = create_comment(
            card=self.card,
            author=self.member,
            body="Original",
        )

    def test_author_can_update_comment(self):
        self.authenticate(
            self.member,
        )

        response = self.client.patch(
            self.detail_url(self.comment),
            data={
                "body": "Updated",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["body"],
            "Updated",
        )

    def test_other_member_cannot_update_comment(self):
        self.authenticate(
            self.other_member,
        )

        response = self.client.patch(
            self.detail_url(self.comment),
            data={
                "body": "Unauthorized",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_workspace_owner_can_update_comment(self):
        self.authenticate(
            self.owner,
        )

        response = self.client.patch(
            self.detail_url(self.comment),
            data={
                "body": "Admin update",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_author_can_delete_comment(self):
        self.authenticate(
            self.member,
        )

        comment_id = self.comment.id

        response = self.client.delete(
            self.detail_url(self.comment),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Comment.objects.filter(
                pk=comment_id,
            ).exists()
        )

    def test_other_member_cannot_delete_comment(self):
        self.authenticate(
            self.other_member,
        )

        response = self.client.delete(
            self.detail_url(self.comment),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_workspace_owner_can_delete_comment(self):
        self.authenticate(
            self.owner,
        )

        response = self.client.delete(
            self.detail_url(self.comment),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )