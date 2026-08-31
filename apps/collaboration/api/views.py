from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.api.permissions import CanViewBoard
from apps.boards.models import Board, Card
from apps.collaboration.api.permissions import CanManageCardAssignees
from apps.collaboration.api.serializers import (
    CardAssigneeCreateSerializer,
    CardAssigneeReadSerializer,
)
from apps.collaboration.models import CardAssignee
from apps.collaboration.services.assignees import (
    add_card_assignee,
    remove_card_assignee,
)
from apps.workspaces.models import WorkspaceMembership


def _raise_api_validation_error(
    exc: DjangoValidationError,
) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc

    raise ValidationError(exc.messages) from exc


def _card_queryset_for_user(user):
    return (
        Card.objects.filter(
            Q(
                board_list__board__workspace__memberships__user=user,
                board_list__board__workspace__memberships__role=(
                    WorkspaceMembership.Role.OWNER
                ),
            )
            | Q(
                board_list__board__memberships__workspace_membership__user=user,
            )
            | Q(
                board_list__board__visibility=Board.Visibility.WORKSPACE,
                board_list__board__workspace__memberships__user=user,
            )
        )
        .select_related(
            "board_list",
            "board_list__board",
            "board_list__board__workspace",
            "created_by",
        )
        .distinct()
    )


def _get_visible_card(
    *,
    user,
    card_id,
) -> Card:
    return get_object_or_404(
        _card_queryset_for_user(user),
        pk=card_id,
    )


def _get_card_workspace_membership(
    *,
    card: Card,
    user_id,
) -> WorkspaceMembership:
    workspace = card.board_list.board.workspace

    try:
        return (
            WorkspaceMembership.objects.select_related(
                "user",
            )
            .get(
                workspace=workspace,
                user_id=user_id,
                user__is_active=True,
            )
        )

    except WorkspaceMembership.DoesNotExist as exc:
        raise ValidationError(
            {
                "user_id": (
                    "An active member of this card's workspace "
                    "with this id was not found."
                )
            }
        ) from exc


class CardAssigneeListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_card(
        self,
        request,
        card_id,
    ) -> Card:
        card = _get_visible_card(
            user=request.user,
            card_id=card_id,
        )

        if not CanViewBoard().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanViewBoard.message
            )

        return card

    @extend_schema(
        responses={
            status.HTTP_200_OK: CardAssigneeReadSerializer(
                many=True,
            )
        },
        tags=["collaboration"],
    )
    def get(
        self,
        request,
        card_id,
    ):
        card = self.get_card(
            request,
            card_id,
        )

        assignees = (
            card.assignees.select_related(
                "workspace_membership__user",
                "assigned_by",
            )
        )

        serializer = CardAssigneeReadSerializer(
            assignees,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CardAssigneeCreateSerializer,
        responses={
            status.HTTP_201_CREATED: CardAssigneeReadSerializer
        },
        tags=["collaboration"],
    )
    def post(
        self,
        request,
        card_id,
    ):
        card = self.get_card(
            request,
            card_id,
        )

        if not CanManageCardAssignees().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanManageCardAssignees.message
            )

        serializer = CardAssigneeCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        workspace_membership = (
            _get_card_workspace_membership(
                card=card,
                user_id=serializer.validated_data[
                    "user_id"
                ],
            )
        )

        try:
            assignee = add_card_assignee(
                card=card,
                workspace_membership=workspace_membership,
                assigned_by=request.user,
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        assignee = (
            CardAssignee.objects.select_related(
                "workspace_membership__user",
                "assigned_by",
            )
            .get(pk=assignee.pk)
        )

        response_serializer = CardAssigneeReadSerializer(
            assignee,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class CardAssigneeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        tags=["collaboration"],
    )
    def delete(
        self,
        request,
        card_id,
        assignee_id,
    ):
        card = _get_visible_card(
            user=request.user,
            card_id=card_id,
        )

        if not CanManageCardAssignees().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanManageCardAssignees.message
            )

        assignee = get_object_or_404(
            CardAssignee.objects.select_related(
                "workspace_membership__user",
            ),
            pk=assignee_id,
            card=card,
        )

        remove_card_assignee(
            assignee=assignee,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )