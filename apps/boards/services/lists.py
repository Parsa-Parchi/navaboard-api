from django.db import transaction

from apps.boards.models import Board, BoardList
from apps.boards.services.ordering import (
    normalize_insert_position,
    normalize_move_position,
    persist_order,
    save_positions,
    vacate_positions,
)


@transaction.atomic
def create_board_list(
    *,
    board: Board,
    title: str,
    position: int | None = None,
) -> BoardList:
    locked_board = Board.objects.select_for_update().get(pk=board.pk)
    queryset = BoardList.objects.select_for_update().filter(board=locked_board)
    existing_lists = list(queryset.order_by("position", "created_at"))
    target_position = normalize_insert_position(position, count=len(existing_lists))

    target_positions = [
        index if index < target_position else index + 1
        for index in range(len(existing_lists))
    ]
    vacate_positions(queryset)
    save_positions(existing_lists, positions=target_positions)

    board_list = BoardList(
        board=locked_board,
        title=title,
        position=target_position,
    )
    board_list.full_clean()
    board_list.save()
    return board_list


@transaction.atomic
def move_board_list(*, board_list: BoardList, position: int) -> BoardList:
    locked_board = Board.objects.select_for_update().get(pk=board_list.board_id)
    queryset = BoardList.objects.select_for_update().filter(board=locked_board)
    ordered_lists = list(queryset.order_by("position", "created_at"))
    target_position = normalize_move_position(position, count=len(ordered_lists))
    moving_list = next(item for item in ordered_lists if item.pk == board_list.pk)

    ordered_lists.remove(moving_list)
    ordered_lists.insert(target_position, moving_list)
    persist_order(queryset, ordered_lists)
    return moving_list


@transaction.atomic
def delete_board_list(*, board_list: BoardList) -> None:
    locked_board = Board.objects.select_for_update().get(pk=board_list.board_id)
    locked_list = BoardList.objects.select_for_update().get(
        pk=board_list.pk,
        board=locked_board,
    )
    locked_list.delete()

    queryset = BoardList.objects.select_for_update().filter(board=locked_board)
    remaining_lists = list(queryset.order_by("position", "created_at"))
    persist_order(queryset, remaining_lists)

