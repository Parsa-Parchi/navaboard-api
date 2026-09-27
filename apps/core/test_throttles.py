from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.activity.models import Activity
from apps.workspaces.models import Workspace


class ActionLimitTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(phone_number="09121234501")
        self.other = get_user_model().objects.create_user(phone_number="09121234502")
        self.client.force_authenticate(self.user)

    @patch("apps.core.throttles.ActionRateThrottle.get_rate", return_value="1/minute")
    def test_mutations_share_budget_and_rejection_has_no_side_effects(self, _):
        response = self.client.post("/api/workspaces/", {"name": "First"})
        self.assertEqual(response.status_code, 201)
        count = Activity.objects.count()
        response = self.client.patch(f'/api/workspaces/{response.data["id"]}/', {"name": "Second"})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(Workspace.objects.get().name, "First")
        self.assertEqual(Activity.objects.count(), count)
        self.assertEqual(self.client.get("/api/workspaces/").status_code, 200)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post("/api/workspaces/", {"name": "Other"}).status_code, 201)

    @patch("apps.core.throttles.SearchRateThrottle.get_rate", return_value="1/minute")
    def test_search_budget_shared_across_resources_but_not_plain_reads(self, _):
        self.assertEqual(self.client.get("/api/workspaces/", {"q": "x"}).status_code, 200)
        self.assertEqual(self.client.get("/api/boards/").status_code, 429)
        self.assertEqual(self.client.get("/api/cards/").status_code, 429)
        self.assertEqual(self.client.get("/api/workspaces/").status_code, 200)

    @patch("apps.core.throttles.ReadRateThrottle.get_rate", return_value="1/minute")
    def test_read_budget_does_not_consume_write_budget(self, _):
        self.assertEqual(self.client.get("/api/workspaces/").status_code, 200)
        self.assertEqual(self.client.get("/api/notifications/unread-count/").status_code, 429)
        self.assertEqual(self.client.post("/api/workspaces/", {"name": "Allowed"}).status_code, 201)

    @patch("apps.core.throttles.ActionRateThrottle.get_rate", return_value="1/minute")
    def test_budget_recovers_after_window(self, _):
        with patch("apps.core.throttles.ActionRateThrottle.timer", return_value=1000):
            self.assertEqual(self.client.post("/api/workspaces/", {"name": "First"}).status_code, 201)
            self.assertEqual(self.client.post("/api/workspaces/", {"name": "Second"}).status_code, 429)
        with patch("apps.core.throttles.ActionRateThrottle.timer", return_value=1061):
            self.assertEqual(self.client.post("/api/workspaces/", {"name": "After"}).status_code, 201)
