from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class WorkspaceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+989121234567")

    def test_cleans_name_and_description(self):
        workspace = Workspace(
            name="  Product Team  ",
            description="  Product workspace  ",
            created_by=self.user,
        )

        workspace.full_clean()

        self.assertEqual(workspace.name, "Product Team")
        self.assertEqual(workspace.description, "Product workspace")

    def test_rejects_blank_name(self):
        workspace = Workspace(name="   ", created_by=self.user)

        with self.assertRaises(ValidationError):
            workspace.full_clean()


class WorkspaceMembershipModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone_number="+989121234567")
        self.member = User.objects.create_user(phone_number="+989121234568")
        self.workspace = Workspace.objects.create(
            name="Product Team",
            created_by=self.owner,
        )
        self.owner_membership = WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )

    def test_rejects_duplicate_membership(self):
        duplicate = WorkspaceMembership(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.MEMBER,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_database_allows_only_one_owner(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=self.member,
                role=WorkspaceMembership.Role.OWNER,
            )

    def test_rejects_unknown_role(self):
        membership = WorkspaceMembership(
            workspace=self.workspace,
            user=self.member,
            role="unknown",
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_owner_is_also_an_admin(self):
        self.assertTrue(self.owner_membership.is_owner)
        self.assertTrue(self.owner_membership.is_admin)

    def test_member_user_is_protected_from_hard_deletion(self):
        with self.assertRaises(ProtectedError):
            self.owner.delete()

