from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db.models import F, Max, QuerySet
from django.utils import timezone


def normalize_insert_position(position: int | None, *, count: int) -> int:
    if position is None:
        return count
    if position < 0 or position > count:
        raise ValidationError(
            {"position": f"Position must be between 0 and {count}."}
        )
    return position


def normalize_move_position(position: int, *, count: int) -> int:
    if position < 0 or position >= count:
        raise ValidationError(
            {"position": f"Position must be between 0 and {count - 1}."}
        )
    return position


def vacate_positions(queryset: QuerySet) -> None:
    count = queryset.count()
    if count == 0:
        return

    maximum = queryset.aggregate(maximum=Max("position"))["maximum"] or 0
    queryset.update(position=F("position") + maximum + count + 1)


def save_positions(items: Iterable, *, positions: Iterable[int] | None = None) -> None:
    items = list(items)
    if not items:
        return

    target_positions = list(positions) if positions is not None else list(range(len(items)))
    now = timezone.now()
    for item, position in zip(items, target_positions, strict=True):
        item.position = position
        item.updated_at = now

    items[0].__class__.objects.bulk_update(
        items,
        fields=("position", "updated_at"),
    )


def persist_order(queryset: QuerySet, items: Iterable) -> None:
    items = list(items)
    vacate_positions(queryset)
    save_positions(items)

