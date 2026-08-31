from rest_framework.permissions import BasePermission

from apps.boards.api.permissions import (
    CanEditBoard,
    IsBoardAdmin,
)


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

class CanModifyComment(BasePermission):
    message = (
        "Only the comment author or a board administrator "
        "can modify this comment."
    )

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if obj.author_id == request.user.id:
            return True

        return IsBoardAdmin().has_object_permission(
            request,
            view,
            obj.card,
        )
class CanManageBoardLabels(BasePermission):
    message = (
        "Board administrator access is required "
        "to manage board labels."
    )

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


class CanManageCardLabels(BasePermission):
    message = (
        "Board edit access is required "
        "to manage card labels."
    )

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ) -> bool:
        return CanEditBoard().has_object_permission(
            request,
            view,
            obj,
        )