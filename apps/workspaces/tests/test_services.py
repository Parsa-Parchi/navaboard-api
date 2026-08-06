from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.services.memberships import (
    add_workspace_member,
    change_workspace_member_role,
    remove_workspace_member,
)
from apps.workspaces.services.workspaces import (
    create_workspace,
    transfer_workspace_ownership,
)


User = get_user_model()


class WorkspaceServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.member = User.objects.create_user(phone_number="+989121234568")

    def test_creates_workspace_and_owner_membership_atomically(self):
        workspace = create_workspace(
            creator=self.owner,
            name="  Product Team  ",
            description="  Product workspace  ",
        )

        membership = workspace.memberships.get()
        self.assertEqual(workspace.name, "Product Team")
        self.assertEqual(workspace.description, "Product workspace")
        self.assertEqual(membership.user, self.owner)
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)

    def test_rejects_workspace_with_blank_name(self):
        with self.assertRaises(ValidationError):
            create_workspace(creator=self.owner, name="   ")

    def test_adds_member_with_default_role(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")

        membership = add_workspace_member(
            workspace=workspace,
            user=self.member,
        )

        self.assertEqual(membership.role, WorkspaceMembership.Role.MEMBER)

    def test_does_not_assign_owner_through_member_service(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")

        with self.assertRaises(ValidationError):
            add_workspace_member(
                workspace=workspace,
                user=self.member,
                role=WorkspaceMembership.Role.OWNER,
            )

    def test_changes_non_owner_role(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        membership = add_workspace_member(workspace=workspace, user=self.member)

        updated_membership = change_workspace_member_role(
            membership=membership,
            role=WorkspaceMembership.Role.ADMIN,
        )

        self.assertEqual(updated_membership.role, WorkspaceMembership.Role.ADMIN)

    def test_does_not_change_owner_through_member_service(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        owner_membership = workspace.memberships.get(user=self.owner)

        with self.assertRaises(ValidationError):
            change_workspace_member_role(
                membership=owner_membership,
                role=WorkspaceMembership.Role.MEMBER,
            )

    def test_removes_non_owner_member(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        membership = add_workspace_member(workspace=workspace, user=self.member)

        remove_workspace_member(membership=membership)

        self.assertFalse(
            WorkspaceMembership.objects.filter(pk=membership.pk).exists()
        )

    def test_does_not_remove_owner(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        owner_membership = workspace.memberships.get(user=self.owner)

        with self.assertRaises(ValidationError):
            remove_workspace_member(membership=owner_membership)

    def test_transfers_ownership_to_existing_member(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        add_workspace_member(workspace=workspace, user=self.member)

        new_owner_membership = transfer_workspace_ownership(
            workspace=workspace,
            acting_user=self.owner,
            new_owner=self.member,
        )

        old_owner_membership = workspace.memberships.get(user=self.owner)
        self.assertEqual(old_owner_membership.role, WorkspaceMembership.Role.ADMIN)
        self.assertEqual(new_owner_membership.role, WorkspaceMembership.Role.OWNER)
        self.assertEqual(
            workspace.memberships.filter(role=WorkspaceMembership.Role.OWNER).count(),
            1,
        )

    def test_only_current_owner_can_transfer_ownership(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")
        add_workspace_member(workspace=workspace, user=self.member)

        with self.assertRaises(ValidationError):
            transfer_workspace_ownership(
                workspace=workspace,
                acting_user=self.member,
                new_owner=self.owner,
            )

    def test_new_owner_must_already_be_a_member(self):
        workspace = create_workspace(creator=self.owner, name="Product Team")

        with self.assertRaises(ValidationError):
            transfer_workspace_ownership(
                workspace=workspace,
                acting_user=self.owner,
                new_owner=self.member,
            )

