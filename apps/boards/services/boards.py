from django.core.exceptions import ValidationError
from django.db import transaction

from apps.boards.models import (
    Board,
    BoardMembership,
    BoardList,
    Card,
)
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.utils import timezone

@transaction.atomic
def create_board(
    *,
    workspace: Workspace,
    creator,
    name: str,
    description: str = "",
    visibility: str = Board.Visibility.PRIVATE,
) -> Board:
    try:
        creator_membership = WorkspaceMembership.objects.select_for_update().get(
            workspace=workspace,
            user=creator,
        )
    except WorkspaceMembership.DoesNotExist as exc:
        raise ValidationError("The board creator must be a workspace member.") from exc

    board = Board(
        workspace=workspace,
        name=name,
        description=description,
        visibility=visibility,
        created_by=creator,
    )
    board.full_clean()
    board.save()

    membership = BoardMembership(
        board=board,
        workspace_membership=creator_membership,
        role=BoardMembership.Role.ADMIN,
    )
    membership.full_clean()
    membership.save()

    return board


@transaction.atomic
def add_board_member(
    *,
    board: Board,
    workspace_membership: WorkspaceMembership,
    role: str = BoardMembership.Role.MEMBER,
) -> BoardMembership:
    membership = BoardMembership(
        board=board,
        workspace_membership=workspace_membership,
        role=role,
    )
    membership.full_clean()
    membership.save()
    return membership


@transaction.atomic
def change_board_member_role(
    *,
    membership: BoardMembership,
    role: str,
) -> BoardMembership:
    locked_membership = BoardMembership.objects.select_for_update().get(
        pk=membership.pk
    )
    locked_membership.role = role
    locked_membership.full_clean()
    locked_membership.save(update_fields=("role",))
    return locked_membership


@transaction.atomic
def remove_board_member(*, membership: BoardMembership) -> None:
    locked_membership = BoardMembership.objects.select_for_update().get(
        pk=membership.pk
    )
    locked_membership.delete()

@transaction.atomic
def delete_board(*, board: Board) -> None:
    locked_board = Board.objects.select_for_update().get(
        pk=board.pk
    )

    lists = BoardList.objects.select_for_update().filter(
        board=locked_board
    )

    cards = Card.objects.select_for_update().filter(
        board_list__in=lists
    )

    cards.update(
        deleted_at=timezone.now()
    )

    lists.update(
        deleted_at=timezone.now()
    )

    locked_board.delete()