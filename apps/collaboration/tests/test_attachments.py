import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.boards.services.boards import create_board
from apps.boards.services.cards import create_card
from apps.boards.services.lists import create_board_list
from apps.workspaces.services.workspaces import create_workspace


class AttachmentTests(APITestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name, ATTACHMENT_MAX_BYTES=16)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(phone_number="09121234581")
        self.outsider = get_user_model().objects.create_user(phone_number="09121234582")
        workspace = create_workspace(creator=self.user, name="W")
        board = create_board(workspace=workspace, creator=self.user, name="B")
        self.card = create_card(board_list=create_board_list(board=board, title="L"), creator=self.user, title="C")
        self.url = f"/api/cards/{self.card.pk}/attachments/"
        self.client.force_authenticate(self.user)

    def test_upload_private_download_and_delete(self):
        response = self.client.post(self.url, {"file": SimpleUploadedFile("test.html", b"<h1>hello</h1>")}, format="multipart")
        self.assertEqual(response.status_code, 201)
        detail = self.url + str(response.data["id"]) + "/"
        response = self.client.get(detail + "content/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"<h1>hello</h1>")
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(detail + "content/").status_code, 404)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertEqual(self.client.get(detail + "content/").status_code, 404)

    def test_rejects_oversized_upload(self):
        response = self.client.post(self.url, {"file": SimpleUploadedFile("large.txt", b"a" * 17)}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.card.attachments.exists())
