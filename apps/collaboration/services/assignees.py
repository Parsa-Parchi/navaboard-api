from django.core.exceptions import ValidationError
from django.db import transaction

from apps.boards.models import Card
from apps.collaboration.models import CardAssignee
from apps.workspaces.models import WorkspaceMembership


@transaction.atomic
def add_card_assignee(
    *,
    card: Card,
    workspace_membership: WorkspaceMembership,
    assigned_by,
) -> CardAssignee:
    locked_card = (
        Card.objects.select_for_update()
        .select_related(
            "board_list__board__workspace",
        )
        .get(pk=card.pk)
    )

    workspace = locked_card.board_list.board.workspace

    if not WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=assigned_by,
    ).exists():
        raise ValidationError(
            "The assigning user must belong to the card's workspace."
        )

    assignee = CardAssignee(
        card=locked_card,
        workspace_membership=workspace_membership,
        assigned_by=assigned_by,
    )

    assignee.full_clean()
    assignee.save()

    return assignee


@transaction.atomic
def remove_card_assignee(
    *,
    assignee: CardAssignee,
) -> None:
    locked_assignee = CardAssignee.objects.select_for_update().get(
        pk=assignee.pk,
    )

    locked_assignee.delete()