from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.boards.models import BoardList, Card
from apps.boards.services.ordering import (
    normalize_insert_position,
    normalize_move_position,
    persist_order,
    save_positions,
    vacate_positions,
)
from apps.workspaces.models import WorkspaceMembership


def _validate_creator_membership(*, board_list: BoardList, creator) -> None:
    if not WorkspaceMembership.objects.filter(
        workspace=board_list.board.workspace,
        user=creator,
    ).exists():
        raise ValidationError("The card creator must be a workspace member.")


@transaction.atomic
def create_card(
    *,
    board_list: BoardList,
    creator,
    title: str,
    description: str = "",
    due_at=None,
    position: int | None = None,
) -> Card:
    locked_list = BoardList.objects.select_for_update().select_related(
        "board__workspace"
    ).get(pk=board_list.pk)
    _validate_creator_membership(board_list=locked_list, creator=creator)

    queryset = Card.objects.select_for_update().filter(board_list=locked_list)
    existing_cards = list(queryset.order_by("position", "created_at"))
    target_position = normalize_insert_position(position, count=len(existing_cards))
    target_positions = [
        index if index < target_position else index + 1
        for index in range(len(existing_cards))
    ]
    vacate_positions(queryset)
    save_positions(existing_cards, positions=target_positions)

    card = Card(
        board_list=locked_list,
        title=title,
        description=description,
        position=target_position,
        due_at=due_at,
        created_by=creator,
    )
    card.full_clean()
    card.save()
    return card


@transaction.atomic
def move_card(
    *,
    card: Card,
    destination_list: BoardList,
    position: int,
) -> Card:
    locked_lists = {
        item.pk: item
        for item in BoardList.objects.select_for_update()
        .select_related("board")
        .filter(pk__in=(card.board_list_id, destination_list.pk))
        .order_by("pk")
    }
    source_list = locked_lists[card.board_list_id]
    destination_list = locked_lists[destination_list.pk]

    if source_list.board_id != destination_list.board_id:
        raise ValidationError("Cards can only move between lists on the same board.")

    source_queryset = Card.objects.select_for_update().filter(board_list=source_list)
    source_cards = list(source_queryset.order_by("position", "created_at"))
    moving_card = next(item for item in source_cards if item.pk == card.pk)

    if source_list.pk == destination_list.pk:
        target_position = normalize_move_position(position, count=len(source_cards))
        source_cards.remove(moving_card)
        source_cards.insert(target_position, moving_card)
        persist_order(source_queryset, source_cards)
        return moving_card

    destination_queryset = Card.objects.select_for_update().filter(
        board_list=destination_list
    )
    destination_cards = list(
        destination_queryset.order_by("position", "created_at")
    )
    target_position = normalize_insert_position(
        position,
        count=len(destination_cards),
    )

    source_cards.remove(moving_card)
    destination_cards.insert(target_position, moving_card)
    vacate_positions(source_queryset)
    vacate_positions(destination_queryset)

    maximum_destination_position = destination_queryset.aggregate(
        maximum=Max("position")
    )["maximum"] or 0
    temporary_position = maximum_destination_position + 1
    Card.objects.filter(pk=moving_card.pk).update(
        board_list=destination_list,
        position=temporary_position,
        updated_at=timezone.now(),
    )
    moving_card.board_list = destination_list

    save_positions(source_cards)
    save_positions(destination_cards)
    return moving_card


@transaction.atomic
def delete_card(*, card: Card) -> None:
    locked_list = BoardList.objects.select_for_update().get(pk=card.board_list_id)
    locked_card = Card.objects.select_for_update().get(
        pk=card.pk,
        board_list=locked_list,
    )
    locked_card.delete()

    queryset = Card.objects.select_for_update().filter(board_list=locked_list)
    remaining_cards = list(queryset.order_by("position", "created_at"))
    persist_order(queryset, remaining_cards)

