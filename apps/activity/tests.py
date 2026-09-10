from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.boards.services.boards import create_board, add_board_member
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.collaboration.models import CardAssignee
from apps.workspaces.services.workspaces import create_workspace
from apps.workspaces.services.memberships import add_workspace_member
from .models import Activity, Notification


class ActivityTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(phone_number="09121234501")
        self.member = get_user_model().objects.create_user(phone_number="09121234502")
        self.outsider = get_user_model().objects.create_user(phone_number="09121234503")
        self.workspace = create_workspace(creator=self.owner, name="Workspace")
        self.membership = add_workspace_member(workspace=self.workspace, user=self.member)
        self.board = create_board(workspace=self.workspace, creator=self.owner, name="Private")
        self.board_member = add_board_member(board=self.board, workspace_membership=self.membership)
        self.board_list = create_board_list(board=self.board, title="Todo")
        self.card = create_card(board_list=self.board_list, creator=self.owner, title="Task")
        CardAssignee.objects.create(card=self.card, workspace_membership=self.membership, assigned_by=self.owner)
        self.client.force_authenticate(self.owner)

    def comment(self):
        return self.client.post(f"/api/cards/{self.card.pk}/comments/", {"body": "Review please"})

    def test_comment_records_one_event_and_notifies_assignee_not_actor(self):
        self.assertEqual(self.comment().status_code, 201)
        event = Activity.objects.get()
        self.assertEqual(event.card_id, self.card.pk)
        self.assertEqual(event.actor_id, self.owner.pk)
        self.assertIn("comment-list.post", event.action)
        self.assertEqual(Notification.objects.get().recipient_id, self.member.pk)

    def test_failed_mutation_does_not_record_activity(self):
        response = self.client.post(f"/api/cards/{self.card.pk}/comments/", {"body": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Activity.objects.exists())

    def test_event_failure_rolls_back_domain_mutation(self):
        with patch("apps.activity.services.Activity.objects.create", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                self.comment()
        self.assertFalse(self.card.comments.exists())

    def test_notification_read_is_idempotent_and_private(self):
        self.comment()
        notification = Notification.objects.get()
        url = f"/api/notifications/{notification.pk}/read/"
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get("/api/notifications/unread-count/").data["count"], 1)
        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.client.post(url).data["read_at"], first.data["read_at"])
        self.assertEqual(self.client.get("/api/notifications/unread-count/").data["count"], 0)

    def test_membership_revocation_hides_old_notifications_and_history(self):
        self.comment()
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get("/api/notifications/").data["count"], 1)
        self.board_member.delete()
        self.assertEqual(self.client.get("/api/notifications/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/boards/{self.board.pk}/activity/").status_code, 404)

    def test_workspace_feed_does_not_leak_private_board_to_workspace_member(self):
        self.comment()
        self.board_member.delete()
        self.client.force_authenticate(self.member)
        response = self.client.get(f"/api/workspaces/{self.workspace.pk}/activity/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_mark_all_reads_only_callers_notifications(self):
        self.comment()
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post("/api/notifications/read-all/").data["updated"], 0)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.post("/api/notifications/read-all/").data["updated"], 1)
        self.assertEqual(self.client.post("/api/notifications/read-all/").data["updated"], 0)

    def test_parent_deletion_hides_collaboration_and_search(self):
        for parent in (self.board_list, self.board, self.workspace):
            with self.subTest(parent=type(parent).__name__):
                parent.delete()
                self.assertEqual(self.client.get(f"/api/cards/{self.card.pk}/comments/").status_code, 404)
                self.assertEqual(self.client.get(f"/api/boards/{self.board.pk}/cards/{self.card.pk}/").status_code, 404)
                self.assertEqual(self.client.get("/api/cards/").data["count"], 0)
                parent.restore()

    def test_workspace_creation_and_card_creation_record_correct_scope(self):
        response = self.client.post("/api/workspaces/", {"name": "Another"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(Activity.objects.get().workspace_id), str(response.data["id"]))
        response = self.client.post(f"/api/workspaces/{self.workspace.pk}/boards/", {"name": "New board"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(Activity.objects.first().board_id), str(response.data["id"]))
        response = self.client.post(f"/api/boards/{self.board.pk}/lists/{self.board_list.pk}/cards/", {"title": "New card"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(Activity.objects.first().card_id), str(response.data["id"]))

    def test_workspace_delete_is_owner_only(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(f"/api/workspaces/{self.workspace.pk}/").status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(f"/api/workspaces/{self.workspace.pk}/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/boards/{self.board.pk}/").status_code, 404)

    def test_search_filters_and_isolates_users(self):
        self.assertEqual(self.client.get("/api/cards/?q=Task").data["count"], 1)
        self.assertEqual(self.client.get("/api/cards/?q=missing").data["count"], 0)
        self.assertEqual(self.client.get("/api/cards/?board_id=invalid").status_code, 400)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get("/api/cards/?assigned_to_me=true").data["count"], 1)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get("/api/cards/?q=Task").data["count"], 0)
