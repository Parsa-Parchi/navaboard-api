from rest_framework.permissions import BasePermission

from apps.boards.models import Board, BoardMembership, BoardList, Card
from apps.workspaces.models import WorkspaceMembership


def _get_board(obj) -> Board:
    if isinstance(obj, Board):
        return obj

    if isinstance(obj, BoardMembership):
        return obj.board

    if isinstance(obj, BoardList):
        return obj.board

    if isinstance(obj, Card):
        return obj.board_list.board

    raise TypeError(
        f"Unsupported board permission object: {type(obj)!r}"
    )


def _is_workspace_owner(*, board: Board, user) -> bool:
    return WorkspaceMembership.objects.filter(
        workspace=board.workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER,
    ).exists()


def _is_workspace_member(*, board: Board, user) -> bool:
    return WorkspaceMembership.objects.filter(
        workspace=board.workspace,
        user=user,
    ).exists()


def _board_membership_for_user(*, board: Board, user):
    return BoardMembership.objects.filter(
        board=board,
        workspace_membership__user=user,
    ).first()


class CanViewBoard(BasePermission):
    message = "You do not have access to this board."

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        board = _get_board(obj)

        if _is_workspace_owner(
            board=board,
            user=request.user,
        ):
            return True

        membership = _board_membership_for_user(
            board=board,
            user=request.user,
        )

        if membership is not None:
            return True

        return (
            board.visibility == Board.Visibility.WORKSPACE
            and _is_workspace_member(
                board=board,
                user=request.user,
            )
        )


class CanEditBoard(BasePermission):
    message = "Board membership is required to edit board content."

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        board = _get_board(obj)

        if _is_workspace_owner(
            board=board,
            user=request.user,
        ):
            return True

        return (
            _board_membership_for_user(
                board=board,
                user=request.user,
            )
            is not None
        )


class IsBoardAdmin(BasePermission):
    message = "Board administrator access is required."

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        board = _get_board(obj)

        if _is_workspace_owner(
            board=board,
            user=request.user,
        ):
            return True

        return BoardMembership.objects.filter(
            board=board,
            workspace_membership__user=request.user,
            role=BoardMembership.Role.ADMIN,
        ).exists()