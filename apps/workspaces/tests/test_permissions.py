from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.workspaces.api.permissions import (
    IsWorkspaceAdmin,
    IsWorkspaceMember,
    IsWorkspaceOwner,
)
from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class WorkspacePermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.admin = User.objects.create_user(phone_number="+989121234568")
        self.member = User.objects.create_user(phone_number="+989121234569")
        self.outsider = User.objects.create_user(phone_number="+989121234570")
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        add_workspace_member(
            workspace=self.workspace,
            user=self.admin,
            role=WorkspaceMembership.Role.ADMIN,
        )
        add_workspace_member(workspace=self.workspace, user=self.member)

    def _request_for(self, user):
        request = self.factory.get("/")
        force_authenticate(request, user=user)
        return APIView().initialize_request(request)

    def test_member_permission_allows_every_workspace_role(self):
        permission = IsWorkspaceMember()

        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.owner), None, self.workspace
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.admin), None, self.workspace
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.member), None, self.workspace
            )
        )

    def test_member_permission_rejects_outsider(self):
        self.assertFalse(
            IsWorkspaceMember().has_object_permission(
                self._request_for(self.outsider), None, self.workspace
            )
        )

    def test_admin_permission_allows_owner_and_admin(self):
        permission = IsWorkspaceAdmin()

        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.owner), None, self.workspace
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.admin), None, self.workspace
            )
        )
        self.assertFalse(
            permission.has_object_permission(
                self._request_for(self.member), None, self.workspace
            )
        )

    def test_owner_permission_only_allows_owner(self):
        permission = IsWorkspaceOwner()

        self.assertTrue(
            permission.has_object_permission(
                self._request_for(self.owner), None, self.workspace
            )
        )
        self.assertFalse(
            permission.has_object_permission(
                self._request_for(self.admin), None, self.workspace
            )
        )
