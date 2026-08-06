from django.core.exceptions import ValidationError
from django.db import transaction

from apps.workspaces.models import Workspace, WorkspaceMembership


@transaction.atomic
def add_workspace_member(
    *,
    workspace: Workspace,
    user,
    role: str = WorkspaceMembership.Role.MEMBER,
) -> WorkspaceMembership:
    if role == WorkspaceMembership.Role.OWNER:
        raise ValidationError("Use the ownership transfer service to assign an owner.")

    membership = WorkspaceMembership(
        workspace=workspace,
        user=user,
        role=role,
    )
    membership.full_clean()
    membership.save()

    return membership


@transaction.atomic
def change_workspace_member_role(
    *,
    membership: WorkspaceMembership,
    role: str,
) -> WorkspaceMembership:
    locked_membership = WorkspaceMembership.objects.select_for_update().get(
        pk=membership.pk
    )

    if locked_membership.role == WorkspaceMembership.Role.OWNER:
        raise ValidationError("The owner role can only be changed by transferring ownership.")

    if role == WorkspaceMembership.Role.OWNER:
        raise ValidationError("Use the ownership transfer service to assign an owner.")

    locked_membership.role = role
    locked_membership.full_clean()
    locked_membership.save(update_fields=("role",))

    return locked_membership


@transaction.atomic
def remove_workspace_member(*, membership: WorkspaceMembership) -> None:
    locked_membership = WorkspaceMembership.objects.select_for_update().get(
        pk=membership.pk
    )

    if locked_membership.role == WorkspaceMembership.Role.OWNER:
        raise ValidationError("Transfer ownership before removing the workspace owner.")

    locked_membership.delete()

