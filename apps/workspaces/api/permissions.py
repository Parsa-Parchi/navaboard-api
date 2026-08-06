from rest_framework.permissions import BasePermission

from apps.workspaces.models import Workspace, WorkspaceMembership


def _get_workspace(obj) -> Workspace:
    if isinstance(obj, Workspace):
        return obj
    return obj.workspace


class IsWorkspaceMember(BasePermission):
    message = "You must be a workspace member to perform this action."

    def has_object_permission(self, request, view, obj) -> bool:
        workspace = _get_workspace(obj)
        return WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=request.user,
        ).exists()


class IsWorkspaceAdmin(BasePermission):
    message = "Workspace administrator access is required."

    def has_object_permission(self, request, view, obj) -> bool:
        workspace = _get_workspace(obj)
        return WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=request.user,
            role__in=(
                WorkspaceMembership.Role.OWNER,
                WorkspaceMembership.Role.ADMIN,
            ),
        ).exists()


class IsWorkspaceOwner(BasePermission):
    message = "Workspace owner access is required."

    def has_object_permission(self, request, view, obj) -> bool:
        workspace = _get_workspace(obj)
        return WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=request.user,
            role=WorkspaceMembership.Role.OWNER,
        ).exists()

