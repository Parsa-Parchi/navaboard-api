from django.db.models import Q

from apps.boards.models import Board, BoardList, Card
from apps.collaboration.models import Checklist, ChecklistItem, Comment
from apps.workspaces.models import Workspace, WorkspaceMembership
from .models import Activity, Notification


def visible_activities(user):
    """Recheck current access so removing a member also hides old notifications."""
    from apps.boards.api.views import _board_queryset_for_user

    boards = _board_queryset_for_user(user).values("pk")
    return Activity.objects.filter(
        workspace__deleted_at__isnull=True,
        workspace__memberships__user=user,
    ).filter(Q(board__isnull=True) | Q(board_id__in=boards)).distinct()


def resolve_scope(kwargs):
    card = None
    if kwargs.get("card_id"):
        card = Card.objects.filter(pk=kwargs["card_id"]).first()
    for key, model, relation in (
        ("comment_id", Comment, "card"),
        ("checklist_id", Checklist, "card"),
        ("item_id", ChecklistItem, "checklist__card"),
    ):
        if kwargs.get(key):
            obj = model.objects.select_related(relation).filter(pk=kwargs[key]).first()
            if obj:
                card = obj.checklist.card if key == "item_id" else obj.card
    board = card.board_list.board if card else None
    if kwargs.get("board_id"):
        board = Board.objects.filter(pk=kwargs["board_id"]).first()
    workspace = board.workspace if board else None
    if kwargs.get("workspace_id"):
        workspace = Workspace.objects.filter(pk=kwargs["workspace_id"]).first()
    return workspace, board, card


def record_mutation(*, request, response, scope, kwargs):
    workspace, board, card = scope
    route = request.resolver_match.url_name
    data = response.data if isinstance(response.data, dict) else {}
    resource_id = data.get("id") or next((str(v) for k, v in reversed(list(kwargs.items())) if k.endswith("_id")), "")
    # Newly created parents/card are only available after the handler succeeds.
    if request.method == "POST" and data.get("id"):
        if route == "workspace-list":
            workspace = Workspace.objects.get(pk=data["id"])
        elif route == "board-list":
            board = Board.objects.get(pk=data["id"])
            workspace = board.workspace
        elif route == "card-list":
            card = Card.objects.get(pk=data["id"])
    if workspace is None:
        return
    event = Activity.objects.create(
        workspace=workspace, board=board, card=card, actor=request.user,
        action=f"{request.resolver_match.namespace}:{route}.{request.method.lower()}", resource_id=str(resource_id),
    )
    recipients = set()
    if card:
        recipients.update(card.assignees.values_list("workspace_membership__user_id", flat=True))
        if card.created_by_id:
            recipients.add(card.created_by_id)
    # Membership changes are relevant to the workspace owner and affected member.
    if "member" in route or "ownership" in route:
        recipients.update(WorkspaceMembership.objects.filter(workspace=workspace, role="owner").values_list("user_id", flat=True))
        user_data = data.get("user")
        if isinstance(user_data, dict) and user_data.get("id"):
            recipients.add(user_data["id"])
    recipients = {str(pk) for pk in recipients} - {str(request.user.pk)}
    Notification.objects.bulk_create([
        Notification(recipient_id=pk, activity=event) for pk in recipients
    ])
