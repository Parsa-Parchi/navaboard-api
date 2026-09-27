from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.boards.services.boards import create_board, add_board_member
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import CardAssignee, CardLabel, Label, Comment, Checklist, ChecklistItem, Attachment
from apps.workspaces.services.workspaces import create_workspace
from apps.workspaces.services.memberships import add_workspace_member


class SearchTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user(phone_number="09121234501")
        self.member = get_user_model().objects.create_user(phone_number="09121234502")
        self.outsider = get_user_model().objects.create_user(phone_number="09121234503")
        self.workspace = create_workspace(creator=self.owner, name="Product Alpha", description="تیم طراحی")
        self.membership = add_workspace_member(workspace=self.workspace, user=self.member)
        self.board = create_board(workspace=self.workspace, creator=self.owner, name="Sprint Alpha")
        self.board_membership = add_board_member(board=self.board, workspace_membership=self.membership)
        self.todo = create_board_list(board=self.board, title="To Do")
        self.done = create_board_list(board=self.board, title="Done")
        self.card = create_card(board_list=self.todo, creator=self.owner, title="Build Login page", description="OTP mobile")
        self.other = create_card(board_list=self.todo, creator=self.owner, title="Write docs")
        self.label = Label.objects.create(board=self.board, name="Urgent", color="red")
        CardLabel.objects.create(card=self.card, label=self.label)
        CardAssignee.objects.create(card=self.card, workspace_membership=self.membership)
        self.client.force_authenticate(self.member)

    def search(self, **params):
        response = self.client.get("/api/cards/", params)
        self.assertEqual(response.status_code, 200, response.data)
        return {row["id"] for row in response.data["results"]}

    def test_workspace_name_description_and_blank_search(self):
        for q in ["alpha", "طراحی", "  "]:
            response = self.client.get("/api/workspaces/", {"q": q})
            self.assertEqual([row["id"] for row in response.data], [str(self.workspace.pk)])
        self.assertEqual(self.client.get("/api/workspaces/", {"q": "missing"}).data, [])

    def test_workspace_search_does_not_reveal_nonmember_or_deleted_workspace(self):
        hidden = create_workspace(creator=self.outsider, name="Product Alpha")
        self.assertEqual(len(self.client.get("/api/workspaces/", {"q": "alpha"}).data), 1)
        self.workspace.delete()
        self.assertEqual(self.client.get("/api/workspaces/", {"q": "alpha"}).data, [])

    def test_board_search_global_and_workspace_arrays(self):
        response = self.client.get("/api/boards/", {"q": "alpha", "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.board.pk))
        self.assertEqual(response.data["results"][0]["current_user_role"], "member")
        response = self.client.get(f"/api/workspaces/{self.workspace.pk}/boards/", {"q": "SPRINT"})
        self.assertEqual([r["id"] for r in response.data], [str(self.board.pk)])

    def test_board_search_private_visibility_revocation_and_owner(self):
        self.board_membership.delete()
        self.assertEqual(self.client.get("/api/boards/", {"q": "alpha"}).data["count"], 0)
        self.assertEqual(self.search(q="Login"), set())
        self.board.visibility = "workspace"
        self.board.save()
        self.assertEqual(self.client.get("/api/boards/").data["count"], 1)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/boards/").data["count"], 1)

    def test_search_excludes_deleted_ancestors(self):
        for parent in [self.todo, self.board, self.workspace]:
            parent.delete()
            self.assertEqual(self.search(), set())
            if parent != self.todo:
                self.assertEqual(self.client.get("/api/boards/").data["count"], 0)
            parent.restore()

    def test_words_phrases_and_negative_terms(self):
        for q in ['login OTP', '"Login page"', 'login -docs', 'name:login description:mobile', 'board:alpha list:"To Do" @me', 'label:urgent has:members -has:attachments', '#Urgent -#Blocked']:
            with self.subTest(q=q):
                self.assertEqual(self.search(q=q), {str(self.card.pk)})
        self.assertEqual(self.search(q='login docs'), set())
        self.assertEqual(self.search(q='-label:urgent'), {str(self.other.pk)})

    def test_apostrophe_in_plain_text_is_not_a_quote_delimiter(self):
        self.card.title = "User's login"
        self.card.save()
        self.assertEqual(self.search(q="User's"), {str(self.card.pk)})

    def test_outsider_cannot_search_or_filter_private_content(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.search(q="label:Urgent"), set())
        self.assertEqual(self.client.get("/api/boards/", {"q": "Sprint"}).data["count"], 0)
        self.assertEqual(self.client.get(f"/api/boards/{self.board.pk}/", {"q": "login"}).status_code, 404)
        self.assertEqual(self.client.get(f"/api/workspaces/{self.workspace.pk}/boards/", {"q": "Sprint"}).status_code, 404)

    def test_omitted_boolean_filters_do_not_exclude_assigned_cards(self):
        self.assertEqual(self.search(), {str(self.card.pk), str(self.other.pk)})
        self.assertEqual(self.search(assigned_to_me=True), {str(self.card.pk)})
        self.assertEqual(self.search(assigned_to_me=False), {str(self.other.pk)})
        row = self.client.get("/api/cards/", {"q": "login"}).data["results"][0]
        self.assertEqual(row["board_id"], str(self.board.pk))
        self.assertEqual(row["workspace_id"], str(self.workspace.pk))
        self.assertEqual(row["list_title"], self.todo.title)

    def test_related_content_search_ignores_deleted_rows(self):
        comment = Comment.objects.create(card=self.card, author=self.owner, body="needle")
        checklist = Checklist.objects.create(card=self.card, title="Release", position=0)
        item = ChecklistItem.objects.create(checklist=checklist, title="needle", position=0)
        self.assertEqual(self.search(q="comment:needle checklist:needle"), {str(self.card.pk)})
        comment.delete()
        self.assertEqual(self.search(q="comment:needle"), set())
        item.delete()
        self.assertEqual(self.search(q="checklist:needle"), set())
        self.assertEqual(self.search(q="checklist:Release"), {str(self.card.pk)})
        checklist.delete()
        self.assertEqual(self.search(q="checklist:Release"), set())

    def test_label_soft_delete_and_negative_related_filter(self):
        self.label.delete()
        self.assertEqual(self.search(q="label:urgent"), set())
        self.assertEqual(self.search(has_labels=False), {str(self.card.pk), str(self.other.pk)})

    def test_negation_excludes_card_even_with_a_different_active_label(self):
        label = Label.objects.create(board=self.board, name="Other", color="blue")
        CardLabel.objects.create(card=self.card, label=label)
        self.assertEqual(self.search(q="-label:urgent"), {str(self.other.pk)})

    def test_multi_select_and_filter_groups(self):
        self.assertEqual(self.search(label_ids=[str(self.label.pk), str(uuid4())], member_ids=[str(self.member.pk)]), {str(self.card.pk)})
        self.assertEqual(self.search(label_ids=[str(self.label.pk)], assigned_to_me=False), set())
        self.assertEqual(self.search(has_members=False), {str(self.other.pk)})
        self.assertEqual(self.search(list_id=str(self.done.pk)), set())

    def test_due_filters_and_null_deadlines(self):
        self.card.due_at = timezone.now() - timedelta(days=1)
        self.card.save()
        self.assertEqual(self.search(due="overdue"), {str(self.card.pk)})
        self.assertEqual(self.search(q="due:none"), {str(self.other.pk)})
        self.card.due_at = timezone.now() + timedelta(hours=2)
        self.card.save()
        for due in ["day", "week"]:
            self.assertEqual(self.search(due=due), {str(self.card.pk)})

    def test_attachment_filter_ignores_soft_deleted_metadata(self):
        attachment = Attachment.objects.create(card=self.card, original_name="a.txt", size=1, file="test/a.txt")
        self.assertEqual(self.search(has_attachments=True), {str(self.card.pk)})
        attachment.delete()
        self.assertEqual(self.search(has_attachments=True), set())

    def test_board_filter_preserves_empty_columns_and_original_positions(self):
        url = f"/api/boards/{self.board.pk}/"
        response = self.client.get(url, {"q": "docs"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["lists"]), 2)
        self.assertEqual([r["id"] for r in response.data["lists"][0]["cards"]], [str(self.other.pk)])
        self.assertEqual(response.data["lists"][0]["cards"][0]["position"], 1)
        self.assertEqual(response.data["lists"][1]["cards"], [])
        self.assertEqual(len(self.client.get(url).data["lists"][0]["cards"]), 2)

    def test_invalid_queries_return_400(self):
        for params in [{"q": '"unfinished'}, {"q": "is:archived"}, {"q": "has:bad"}, {"q": "label:"}, {"q": "x " * 21}, {"q": "x" * 201}, {"due": "yesterday"}, {"label_ids": ["bad"]}, {"member_ids": [str(uuid4())] * 21}, {"board_id": "bad"}, {"due_after": "2026-10-02T00:00:00Z", "due_before": "2026-10-01T00:00:00Z"}]:
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/cards/", params).status_code, 400)
                self.assertEqual(self.client.get(f"/api/boards/{self.board.pk}/", params).status_code, 400)
        for url in ["/api/workspaces/", "/api/boards/", f"/api/workspaces/{self.workspace.pk}/boards/"]:
            self.assertEqual(self.client.get(url, {"q": "x" * 201}).status_code, 400)

    def test_search_requires_authentication(self):
        self.client.force_authenticate(None)
        for url in ["/api/cards/", "/api/boards/", "/api/workspaces/"]:
            self.assertEqual(self.client.get(url, {"q": "alpha"}).status_code, 401)
