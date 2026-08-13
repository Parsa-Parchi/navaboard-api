from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class BoardDetailHydrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            phone_number="+989121234610",
        )

        self.workspace = create_workspace(
            creator=self.owner,
            name="Product Team",
        )

        self.board = create_board(
            workspace=self.workspace,
            creator=self.owner,
            name="Product Board",
        )

        self.todo = create_board_list(
            board=self.board,
            title="Todo",
        )

        self.doing = create_board_list(
            board=self.board,
            title="Doing",
        )

        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Task 1",
        )

        create_card(
            board_list=self.todo,
            creator=self.owner,
            title="Task 2",
        )

        create_card(
            board_list=self.doing,
            creator=self.owner,
            title="Task 3",
        )

        self.detail_url = reverse(
            "boards-api:board-detail",
            kwargs={
                "board_id": self.board.id,
            },
        )

        self.list_url = reverse(
            "boards-api:board-list",
            kwargs={
                "workspace_id": self.workspace.id,
            },
        )

        self.client.force_authenticate(
            user=self.owner,
        )

    def _detail_query_count(self):
        with CaptureQueriesContext(
            connection
        ) as captured_queries:
            response = self.client.get(
                self.detail_url,
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        return len(captured_queries)

    def test_board_detail_returns_lists_and_cards(
        self,
    ):
        response = self.client.get(
            self.detail_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            str(self.board.id),
        )

        self.assertEqual(
            response.data["current_user_role"],
            "admin",
        )

        self.assertIn(
            "lists",
            response.data,
        )

        self.assertEqual(
            [
                item["title"]
                for item in response.data["lists"]
            ],
            [
                "Todo",
                "Doing",
            ],
        )

        self.assertEqual(
            [
                card["title"]
                for card in response.data[
                    "lists"
                ][0]["cards"]
            ],
            [
                "Task 1",
                "Task 2",
            ],
        )

        self.assertEqual(
            [
                card["title"]
                for card in response.data[
                    "lists"
                ][1]["cards"]
            ],
            [
                "Task 3",
            ],
        )

    def test_board_list_endpoint_remains_summary_only(
        self,
    ):
        response = self.client.get(
            self.list_url,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertNotIn(
            "lists",
            response.data[0],
        )

    def test_detail_query_count_does_not_grow_with_board_size(
        self,
    ):
        self.client.get(
            self.detail_url,
        )

        baseline_query_count = (
            self._detail_query_count()
        )

        for list_index in range(5):
            board_list = create_board_list(
                board=self.board,
                title=f"Extra {list_index}",
            )

            for card_index in range(5):
                create_card(
                    board_list=board_list,
                    creator=self.owner,
                    title=(
                        f"Extra {list_index} "
                        f"Card {card_index}"
                    ),
                )

        expanded_query_count = (
            self._detail_query_count()
        )

        self.assertEqual(
            expanded_query_count,
            baseline_query_count,
        )