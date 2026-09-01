from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.workspaces.models import Workspace, WorkspaceMembership
from apps.workspaces.services.memberships import add_workspace_member
from apps.workspaces.services.workspaces import create_workspace


User = get_user_model()


class WorkspaceAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.admin = User.objects.create_user(phone_number="+989121234568")
        self.member = User.objects.create_user(phone_number="+989121234569")
        self.outsider = User.objects.create_user(phone_number="+989121234570")

    def authenticate(self, user):
        self.client.force_authenticate(user=user)


class WorkspaceListCreateAPIViewTests(WorkspaceAPITestCase):
    def test_requires_authentication(self):
        response = self.client.get(reverse("workspaces-api:workspace-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creates_workspace_and_owner_membership(self):
        self.authenticate(self.owner)

        response = self.client.post(
            reverse("workspaces-api:workspace-list"),
            data={"name": "  Product Team  ", "description": "  Roadmap  "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Product Team")
        self.assertEqual(response.data["description"], "Roadmap")
        self.assertEqual(response.data["current_user_role"], "owner")
        workspace = Workspace.objects.get(pk=response.data["id"])
        self.assertTrue(
            workspace.memberships.filter(
                user=self.owner,
                role=WorkspaceMembership.Role.OWNER,
            ).exists()
        )

    def test_lists_only_users_workspaces(self):
        own_workspace = create_workspace(creator=self.owner, name="Own Team")
        create_workspace(creator=self.outsider, name="Other Team")
        self.authenticate(self.owner)

        response = self.client.get(reverse("workspaces-api:workspace-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(own_workspace.id))
        self.assertEqual(response.data[0]["current_user_role"], "owner")


class WorkspaceDetailAPIViewTests(WorkspaceAPITestCase):
    def setUp(self):
        super().setUp()
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        add_workspace_member(workspace=self.workspace, user=self.member)
        add_workspace_member(
            workspace=self.workspace,
            user=self.admin,
            role=WorkspaceMembership.Role.ADMIN,
        )
        self.url = reverse(
            "workspaces-api:workspace-detail",
            kwargs={"workspace_id": self.workspace.id},
        )

    def test_member_can_retrieve_workspace(self):
        self.authenticate(self.member)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_user_role"], "member")

    def test_outsider_cannot_discover_workspace(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_update_workspace(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.url,
            data={"name": "  Engineering Team  "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Engineering Team")

    def test_member_cannot_update_workspace(self):
        self.authenticate(self.member)

        response = self.client.patch(
            self.url,
            data={"name": "Unauthorized"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, "Product Team")


class WorkspaceMembershipAPIViewTests(WorkspaceAPITestCase):
    def setUp(self):
        super().setUp()
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        self.admin_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.admin,
            role=WorkspaceMembership.Role.ADMIN,
        )
        self.member_membership = add_workspace_member(
            workspace=self.workspace,
            user=self.member,
        )
        self.list_url = reverse(
            "workspaces-api:membership-list",
            kwargs={"workspace_id": self.workspace.id},
        )

    def detail_url(self, membership):
        return reverse(
            "workspaces-api:membership-detail",
            kwargs={
                "workspace_id": self.workspace.id,
                "membership_id": membership.id,
            },
        )

    def test_member_can_list_workspace_members(self):
        self.authenticate(self.member)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_outsider_cannot_list_workspace_members(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_add_admin(self):
        new_user = User.objects.create_user(phone_number="+989121234571")
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            data={"phone_number": new_user.phone_number, "role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "admin")

    def test_admin_can_add_regular_member(self):
        new_user = User.objects.create_user(phone_number="+989121234571")
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            data={"phone_number": new_user.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "member")

    def test_admin_cannot_add_another_admin(self):
        new_user = User.objects.create_user(phone_number="+989121234571")
        self.authenticate(self.admin)

        response = self.client.post(
            self.list_url,
            data={"phone_number": new_user.phone_number, "role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=new_user,
            ).exists()
        )

    def test_member_cannot_add_members(self):
        new_user = User.objects.create_user(phone_number="+989121234571")
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url,
            data={"phone_number": new_user.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_duplicate_membership(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            data={"phone_number": self.member.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_change_member_role(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.detail_url(self.member_membership),
            data={"role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "admin")

    def test_admin_cannot_change_member_role(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(self.member_membership),
            data={"role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_leave_workspace(self):
        self.authenticate(self.member)

        response = self.client.delete(self.detail_url(self.member_membership))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            WorkspaceMembership.objects.filter(pk=self.member_membership.pk).exists()
        )

    def test_admin_can_remove_regular_member(self):
        self.authenticate(self.admin)

        response = self.client.delete(self.detail_url(self.member_membership))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_cannot_remove_owner(self):
        owner_membership = self.workspace.memberships.get(user=self.owner)
        self.authenticate(self.admin)

        response = self.client.delete(self.detail_url(owner_membership))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_must_transfer_ownership_before_leaving(self):
        owner_membership = self.workspace.memberships.get(user=self.owner)
        self.authenticate(self.owner)

        response = self.client.delete(self.detail_url(owner_membership))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            WorkspaceMembership.objects.filter(pk=owner_membership.pk).exists()
        )


class WorkspaceOwnershipTransferAPIViewTests(WorkspaceAPITestCase):
    def setUp(self):
        super().setUp()
        self.workspace = create_workspace(creator=self.owner, name="Product Team")
        add_workspace_member(workspace=self.workspace, user=self.member)
        self.url = reverse(
            "workspaces-api:transfer-ownership",
            kwargs={"workspace_id": self.workspace.id},
        )

    def test_owner_can_transfer_ownership(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.url,
            data={"new_owner_phone_number": self.member.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "owner")
        self.assertEqual(
            self.workspace.memberships.get(user=self.owner).role,
            WorkspaceMembership.Role.ADMIN,
        )

    def test_non_owner_cannot_transfer_ownership(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.url,
            data={"new_owner_phone_number": self.owner.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_owner_must_be_workspace_member(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.url,
            data={"new_owner_phone_number": self.outsider.phone_number},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

