from django.core.exceptions import ValidationError
from django.db import transaction

from apps.boards.models import Board, Card
from apps.collaboration.models import CardLabel, Label


_UNSET = object()


@transaction.atomic
def create_label(
    *,
    board: Board,
    name: str,
    color: str,
) -> Label:
    locked_board = Board.objects.select_for_update().get(
        pk=board.pk,
    )

    label = Label(
        board=locked_board,
        name=name,
        color=color,
    )

    label.full_clean()
    label.save()

    return label


@transaction.atomic
def update_label(
    *,
    label: Label,
    name=_UNSET,
    color=_UNSET,
) -> Label:
    locked_label = Label.objects.select_for_update().get(
        pk=label.pk,
    )

    if name is not _UNSET:
        locked_label.name = name

    if color is not _UNSET:
        locked_label.color = color

    locked_label.full_clean()
    locked_label.save()

    return locked_label


@transaction.atomic
def delete_label(
    *,
    label: Label,
) -> None:
    locked_label = Label.objects.select_for_update().get(
        pk=label.pk,
    )

    locked_label.delete()


@transaction.atomic
def attach_label_to_card(
    *,
    card: Card,
    label: Label,
) -> CardLabel:
    locked_card = (
        Card.objects.select_for_update()
        .select_related(
            "board_list__board",
        )
        .get(pk=card.pk)
    )

    locked_label = Label.objects.select_for_update().get(
        pk=label.pk,
    )

    card_label = CardLabel(
        card=locked_card,
        label=locked_label,
    )

    card_label.full_clean()
    card_label.save()

    return card_label


@transaction.atomic
def detach_label_from_card(
    *,
    card: Card,
    label: Label,
) -> None:
    card_label = (
        CardLabel.objects.select_for_update()
        .get(
            card=card,
            label=label,
        )
    )

    card_label.delete()