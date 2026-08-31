from rest_framework.permissions import BasePermission

from apps.boards.api.permissions import IsBoardAdmin


class CanManageCardAssignees(BasePermission):
    message = "Board administrator access is required to manage card assignees."

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ) -> bool:
        return IsBoardAdmin().has_object_permission(
            request,
            view,
            obj,
        )