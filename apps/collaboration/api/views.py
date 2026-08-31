from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.api.permissions import (
    CanEditBoard,
    CanViewBoard,
)
from apps.boards.models import Board, Card
from apps.collaboration.api.permissions import (
    CanManageCardAssignees,
    CanModifyComment,
)
from apps.collaboration.api.serializers import (
    CardAssigneeCreateSerializer,
    CardAssigneeReadSerializer,
    CommentCreateSerializer,
    CommentReadSerializer,
    CommentUpdateSerializer,
)
from apps.collaboration.models import (
    CardAssignee,
    Comment,
)
from apps.collaboration.services.assignees import (
    add_card_assignee,
    remove_card_assignee,
)

from apps.collaboration.services.comments import (
    create_comment,
    delete_comment,
    update_comment,
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

class CommentListCreateAPIView(APIView):
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
            status.HTTP_200_OK: CommentReadSerializer(
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

        comments = card.comments.select_related(
            "author",
        )

        serializer = CommentReadSerializer(
            comments,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CommentCreateSerializer,
        responses={
            status.HTTP_201_CREATED: CommentReadSerializer
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

        if not CanEditBoard().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = CommentCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            comment = create_comment(
                card=card,
                author=request.user,
                body=serializer.validated_data["body"],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        comment = Comment.objects.select_related(
            "author",
        ).get(
            pk=comment.pk,
        )

        response_serializer = CommentReadSerializer(
            comment,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_comment(
        self,
        request,
        comment_id,
    ) -> Comment:
        comment = get_object_or_404(
            Comment.objects.select_related(
                "author",
                "card",
                "card__board_list",
                "card__board_list__board",
                "card__board_list__board__workspace",
            ),
            pk=comment_id,
        )

        visible_card = _get_visible_card(
            user=request.user,
            card_id=comment.card_id,
        )

        if not CanViewBoard().has_object_permission(
            request,
            self,
            visible_card,
        ):
            raise PermissionDenied(
                CanViewBoard.message
            )

        return comment

    @extend_schema(
        request=CommentUpdateSerializer,
        responses={
            status.HTTP_200_OK: CommentReadSerializer
        },
        tags=["collaboration"],
    )
    def patch(
        self,
        request,
        comment_id,
    ):
        comment = self.get_comment(
            request,
            comment_id,
        )

        if not CanModifyComment().has_object_permission(
            request,
            self,
            comment,
        ):
            raise PermissionDenied(
                CanModifyComment.message
            )

        serializer = CommentUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            comment = update_comment(
                comment=comment,
                body=serializer.validated_data["body"],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        comment = Comment.objects.select_related(
            "author",
        ).get(
            pk=comment.pk,
        )

        response_serializer = CommentReadSerializer(
            comment,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        tags=["collaboration"],
    )
    def delete(
        self,
        request,
        comment_id,
    ):
        comment = self.get_comment(
            request,
            comment_id,
        )

        if not CanModifyComment().has_object_permission(
            request,
            self,
            comment,
        ):
            raise PermissionDenied(
                CanModifyComment.message
            )

        delete_comment(
            comment=comment,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )