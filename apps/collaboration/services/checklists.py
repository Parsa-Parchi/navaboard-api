from django.core.exceptions import ValidationError
from django.db import transaction

from apps.boards.models import Card
from apps.collaboration.models import (
    Checklist,
    ChecklistItem,
)


_UNSET = object()


def _resequence(objects) -> None:
    if not objects:
        return

    model = objects[0].__class__

    for index, obj in enumerate(objects):
        model.objects.filter(pk=obj.pk).update(
            position=1000000 + index
        )

    for index, obj in enumerate(objects):
        model.objects.filter(pk=obj.pk).update(
            position=index
        )
        obj.position = index


@transaction.atomic
def create_checklist(
    *,
    card: Card,
    title: str,
) -> Checklist:
    locked_card = Card.objects.select_for_update().get(
        pk=card.pk,
    )

    siblings = list(
        Checklist.objects.select_for_update()
        .filter(card=locked_card)
        .order_by(
            "position",
            "created_at",
        )
    )

    position = (
        max(
            checklist.position
            for checklist in siblings
        )
        + 1
        if siblings
        else 0
    )

    checklist = Checklist(
        card=locked_card,
        title=title,
        position=position,
    )

    checklist.full_clean()
    checklist.save()

    return checklist


@transaction.atomic
def update_checklist(
    *,
    checklist: Checklist,
    title: str,
) -> Checklist:
    locked_checklist = (
        Checklist.objects.select_for_update()
        .get(pk=checklist.pk)
    )

    locked_checklist.title = title
    locked_checklist.full_clean()
    locked_checklist.save()

    return locked_checklist


@transaction.atomic
def move_checklist(
    *,
    checklist: Checklist,
    position: int,
) -> Checklist:
    siblings = list(
        Checklist.objects.select_for_update()
        .filter(card_id=checklist.card_id)
        .order_by(
            "position",
            "created_at",
        )
    )

    if position < 0 or position >= len(siblings):
        raise ValidationError(
            {
                "position": (
                    "Position is outside the valid "
                    "checklist range."
                )
            }
        )

    current_index = next(
        (
            index
            for index, sibling
            in enumerate(siblings)
            if sibling.pk == checklist.pk
        ),
        None,
    )

    if current_index is None:
        raise ValidationError(
            "Checklist was not found in its card."
        )

    moving = siblings.pop(current_index)
    siblings.insert(
        position,
        moving,
    )

    _resequence(siblings)

    moving.refresh_from_db()

    return moving


@transaction.atomic
def delete_checklist(
    *,
    checklist: Checklist,
) -> None:
    siblings = list(
        Checklist.objects.select_for_update()
        .filter(card_id=checklist.card_id)
        .order_by(
            "position",
            "created_at",
        )
    )

    locked_checklist = next(
        (
            sibling
            for sibling in siblings
            if sibling.pk == checklist.pk
        ),
        None,
    )

    if locked_checklist is None:
        raise ValidationError(
            "Checklist was not found."
        )

    locked_checklist.delete()

    remaining = list(
        Checklist.objects.select_for_update()
        .filter(
            card_id=checklist.card_id,
        )
        .order_by(
            "position",
            "created_at",
        )
    )

    _resequence(remaining)

@transaction.atomic
def create_checklist_item(
    *,
    checklist: Checklist,
    title: str,
) -> ChecklistItem:
    locked_checklist = (
        Checklist.objects.select_for_update()
        .get(pk=checklist.pk)
    )

    siblings = list(
        ChecklistItem.objects.select_for_update()
        .filter(checklist=locked_checklist)
        .order_by(
            "position",
            "created_at",
        )
    )

    position = (
        max(
            item.position
            for item in siblings
        )
        + 1
        if siblings
        else 0
    )

    item = ChecklistItem(
        checklist=locked_checklist,
        title=title,
        position=position,
    )

    item.full_clean()
    item.save()

    return item


@transaction.atomic
def update_checklist_item(
    *,
    item: ChecklistItem,
    title=_UNSET,
    is_completed=_UNSET,
) -> ChecklistItem:
    locked_item = (
        ChecklistItem.objects.select_for_update()
        .get(pk=item.pk)
    )

    if title is not _UNSET:
        locked_item.title = title

    if is_completed is not _UNSET:
        locked_item.is_completed = is_completed

    locked_item.full_clean()
    locked_item.save()

    return locked_item


@transaction.atomic
def move_checklist_item(
    *,
    item: ChecklistItem,
    position: int,
) -> ChecklistItem:
    siblings = list(
        ChecklistItem.objects.select_for_update()
        .filter(
            checklist_id=item.checklist_id,
        )
        .order_by(
            "position",
            "created_at",
        )
    )

    if position < 0 or position >= len(siblings):
        raise ValidationError(
            {
                "position": (
                    "Position is outside the valid "
                    "checklist item range."
                )
            }
        )

    current_index = next(
        (
            index
            for index, sibling
            in enumerate(siblings)
            if sibling.pk == item.pk
        ),
        None,
    )

    if current_index is None:
        raise ValidationError(
            "Checklist item was not found."
        )

    moving = siblings.pop(current_index)
    siblings.insert(
        position,
        moving,
    )

    _resequence(siblings)

    moving.refresh_from_db()

    return moving


@transaction.atomic
def delete_checklist_item(
    *,
    item: ChecklistItem,
) -> None:
    siblings = list(
        ChecklistItem.objects.select_for_update()
        .filter(
            checklist_id=item.checklist_id,
        )
        .order_by(
            "position",
            "created_at",
        )
    )

    locked_item = next(
        (
            sibling
            for sibling in siblings
            if sibling.pk == item.pk
        ),
        None,
    )

    if locked_item is None:
        raise ValidationError(
            "Checklist item was not found."
        )

    locked_item.delete()

    remaining = list(
        ChecklistItem.objects.select_for_update()
        .filter(
            checklist_id=item.checklist_id,
        )
        .order_by(
            "position",
            "created_at",
        )
    )

    _resequence(remaining)