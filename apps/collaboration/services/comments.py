from django.core.exceptions import ValidationError
from django.db import transaction

from apps.boards.models import Card
from apps.collaboration.models import Comment
from apps.workspaces.models import WorkspaceMembership


@transaction.atomic
def create_comment(
    *,
    card: Card,
    author,
    body: str,
) -> Comment:
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
        user=author,
    ).exists():
        raise ValidationError(
            "The comment author must belong to the card's workspace."
        )

    comment = Comment(
        card=locked_card,
        author=author,
        body=body,
    )

    comment.full_clean()
    comment.save()

    return comment


@transaction.atomic
def update_comment(
    *,
    comment: Comment,
    body: str,
) -> Comment:
    locked_comment = (
        Comment.objects.select_for_update()
        .select_related(
            "card__board_list__board__workspace",

        )
        .get(pk=comment.pk)
    )

    locked_comment.body = body
    locked_comment.full_clean()
    locked_comment.save()

    return locked_comment


@transaction.atomic
def delete_comment(
    *,
    comment: Comment,
) -> None:
    locked_comment = Comment.objects.select_for_update().get(
        pk=comment.pk,
    )

    locked_comment.delete()