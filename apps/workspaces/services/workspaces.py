from django.core.exceptions import ValidationError
from django.db import transaction

from apps.workspaces.models import Workspace, WorkspaceMembership


@transaction.atomic
def create_workspace(*, creator, name: str, description: str = "") -> Workspace:
    if creator is None or creator.pk is None:
        raise ValidationError("A saved user is required to create a workspace.")

    workspace = Workspace(
        name=name,
        description=description,
        created_by=creator,
    )
    workspace.full_clean()
    workspace.save()

    owner_membership = WorkspaceMembership(
        workspace=workspace,
        user=creator,
        role=WorkspaceMembership.Role.OWNER,
    )
    owner_membership.full_clean()
    owner_membership.save()

    return workspace


@transaction.atomic
def transfer_workspace_ownership(
    *,
    workspace: Workspace,
    acting_user,
    new_owner,
) -> WorkspaceMembership:
    if workspace.pk is None:
        raise ValidationError("A saved workspace is required.")

    locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
    memberships = WorkspaceMembership.objects.select_for_update().filter(
        workspace=locked_workspace,
        user__in=(acting_user, new_owner),
    )
    memberships_by_user_id = {
        membership.user_id: membership for membership in memberships
    }

    current_owner_membership = memberships_by_user_id.get(acting_user.pk)
    if (
        current_owner_membership is None
        or current_owner_membership.role != WorkspaceMembership.Role.OWNER
    ):
        raise ValidationError("Only the current workspace owner can transfer ownership.")

    new_owner_membership = memberships_by_user_id.get(new_owner.pk)
    if new_owner_membership is None:
        raise ValidationError("The new owner must already be a workspace member.")

    if new_owner_membership.pk == current_owner_membership.pk:
        raise ValidationError("The new owner must be a different workspace member.")

    current_owner_membership.role = WorkspaceMembership.Role.ADMIN
    current_owner_membership.full_clean()
    current_owner_membership.save(update_fields=("role",))

    new_owner_membership.role = WorkspaceMembership.Role.OWNER
    new_owner_membership.full_clean()
    new_owner_membership.save(update_fields=("role",))

    return new_owner_membership

