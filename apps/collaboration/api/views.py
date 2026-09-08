
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
    CanManageBoardLabels,
    CanManageCardAssignees,
    CanManageCardLabels,
    CanModifyComment,
)
from apps.collaboration.api.serializers import (
    CardAssigneeCreateSerializer,
    CardAssigneeReadSerializer,
    CommentCreateSerializer,
    CommentReadSerializer,
    CommentUpdateSerializer,
    CardLabelCreateSerializer,
    CardLabelReadSerializer,
    LabelCreateSerializer,
    LabelReadSerializer,
    LabelUpdateSerializer,
    ChecklistCreateSerializer,
    ChecklistItemCreateSerializer,
    ChecklistItemReadSerializer,
    ChecklistItemUpdateSerializer,
    ChecklistReadSerializer,
    ChecklistUpdateSerializer,
    PositionSerializer,
)
from apps.collaboration.models import (
    CardAssignee,
    Comment,
    CardLabel,
    Label,
    Checklist,
    ChecklistItem,
)

from apps.collaboration.services.labels import (
    attach_label_to_card,
    create_label,
    delete_label,
    detach_label_from_card,
    update_label,
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


from apps.collaboration.services.checklists import (
    create_checklist,
    create_checklist_item,
    delete_checklist,
    delete_checklist_item,
    move_checklist,
    move_checklist_item,
    update_checklist,
    update_checklist_item,
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

def _board_queryset_for_user(user):
    return (
        Board.objects.filter(
            Q(
                workspace__memberships__user=user,
                workspace__memberships__role=(
                    WorkspaceMembership.Role.OWNER
                ),
            )
            | Q(
                memberships__workspace_membership__user=user,
            )
            | Q(
                visibility=Board.Visibility.WORKSPACE,
                workspace__memberships__user=user,
            )
        )
        .select_related(
            "workspace",
        )
        .distinct()
    )


def _get_visible_board(
    *,
    user,
    board_id,
) -> Board:
    return get_object_or_404(
        _board_queryset_for_user(user),
        pk=board_id,
    )


def _get_card_workspace_membership(
    *,
    card: Card,
    phone_number,
) -> WorkspaceMembership:
    workspace = card.board_list.board.workspace

    try:
        return (
            WorkspaceMembership.objects.select_related(
                "user",
            )
            .get(
                workspace=workspace,
                user__phone_number=phone_number,
                user__is_active=True,
            )
        )

    except WorkspaceMembership.DoesNotExist as exc:
        raise ValidationError(
            {
                "phone_number": (
    "An active member of this card's workspace "
    "with this phone number was not found."
)
            }
        ) from exc

def _get_visible_checklist(
    *,
    user,
    checklist_id,
) -> Checklist:
    checklist = get_object_or_404(
        Checklist.objects.select_related(
            "card",
            "card__board_list",
            "card__board_list__board",
        ),
        pk=checklist_id,
    )

    _get_visible_card(
        user=user,
        card_id=checklist.card_id,
    )

    return checklist


def _get_visible_checklist_item(
    *,
    user,
    item_id,
) -> ChecklistItem:
    item = get_object_or_404(
        ChecklistItem.objects.select_related(
            "checklist",
            "checklist__card",
            "checklist__card__board_list",
            "checklist__card__board_list__board",
        ),
        pk=item_id,
    )

    _get_visible_card(
        user=user,
        card_id=item.checklist.card_id,
    )

    return item


class BoardLabelListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_board(
        self,
        request,
        board_id,
    ) -> Board:
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        if not CanViewBoard().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanViewBoard.message
            )

        return board

    @extend_schema(
        responses={
            status.HTTP_200_OK: LabelReadSerializer(
                many=True,
            )
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def get(
        self,
        request,
        board_id,
    ):
        board = self.get_board(
            request,
            board_id,
        )

        labels = board.labels.all()

        serializer = LabelReadSerializer(
            labels,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=LabelCreateSerializer,
        responses={
            status.HTTP_201_CREATED: LabelReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        board_id,
    ):
        board = self.get_board(
            request,
            board_id,
        )

        if not CanManageBoardLabels().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanManageBoardLabels.message
            )

        serializer = LabelCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            label = create_label(
                board=board,
                name=serializer.validated_data["name"],
                color=serializer.validated_data["color"],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = LabelReadSerializer(
            label,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class BoardLabelDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_board_and_label(
        self,
        request,
        board_id,
        label_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        label = get_object_or_404(
            Label,
            pk=label_id,
            board=board,
        )

        return board, label

    @extend_schema(
        request=LabelUpdateSerializer,
        responses={
            status.HTTP_200_OK: LabelReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def patch(
        self,
        request,
        board_id,
        label_id,
    ):
        board, label = self.get_board_and_label(
            request,
            board_id,
            label_id,
        )

        if not CanManageBoardLabels().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanManageBoardLabels.message
            )

        serializer = LabelUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            label = update_label(
                label=label,
                **serializer.validated_data,
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = LabelReadSerializer(
            label,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def delete(
        self,
        request,
        board_id,
        label_id,
    ):
        board, label = self.get_board_and_label(
            request,
            board_id,
            label_id,
        )

        if not CanManageBoardLabels().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanManageBoardLabels.message
            )

        delete_label(
            label=label,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class CardLabelCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CardLabelCreateSerializer,
        responses={
            status.HTTP_201_CREATED: CardLabelReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        card_id,
    ):
        card = _get_visible_card(
            user=request.user,
            card_id=card_id,
        )

        if not CanManageCardLabels().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanManageCardLabels.message
            )

        serializer = CardLabelCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            label = Label.objects.get(
                pk=serializer.validated_data["label_id"],
                board_id=card.board_list.board_id,
            )

        except Label.DoesNotExist as exc:
            raise ValidationError(
                {
                    "label_id": (
                        "A label belonging to this card's board "
                        "with this id was not found."
                    )
                }
            ) from exc

        try:
            card_label = attach_label_to_card(
                card=card,
                label=label,
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        card_label = (
            CardLabel.objects.select_related(
                "label",
                "label__board",
            )
            .get(pk=card_label.pk)
        )

        response_serializer = CardLabelReadSerializer(
            card_label,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class CardLabelDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def delete(
        self,
        request,
        card_id,
        label_id,
    ):
        card = _get_visible_card(
            user=request.user,
            card_id=card_id,
        )

        if not CanManageCardLabels().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanManageCardLabels.message
            )

        label = get_object_or_404(
            Label,
            pk=label_id,
            board_id=card.board_list.board_id,
        )

        get_object_or_404(
            CardLabel,
            card=card,
            label=label,
        )

        detach_label_from_card(
            card=card,
            label=label,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class ChecklistListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            status.HTTP_200_OK: ChecklistReadSerializer(
                many=True,
            )
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def get(
        self,
        request,
        card_id,
    ):
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

        checklists = (
            card.checklists.prefetch_related(
                "items",
            )
        )

        serializer = ChecklistReadSerializer(
            checklists,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ChecklistCreateSerializer,
        responses={
            status.HTTP_201_CREATED: ChecklistReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        card_id,
    ):
        card = _get_visible_card(
            user=request.user,
            card_id=card_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = ChecklistCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            checklist = create_checklist(
                card=card,
                title=serializer.validated_data[
                    "title"
                ],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = ChecklistReadSerializer(
            checklist,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ChecklistDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChecklistUpdateSerializer,
        responses={
            status.HTTP_200_OK: ChecklistReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def patch(
        self,
        request,
        checklist_id,
    ):
        checklist = _get_visible_checklist(
            user=request.user,
            checklist_id=checklist_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = ChecklistUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            checklist = update_checklist(
                checklist=checklist,
                title=serializer.validated_data[
                    "title"
                ],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = ChecklistReadSerializer(
            checklist,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def delete(
        self,
        request,
        checklist_id,
    ):
        checklist = _get_visible_checklist(
            user=request.user,
            checklist_id=checklist_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        delete_checklist(
            checklist=checklist,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class ChecklistMoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PositionSerializer,
        responses={
            status.HTTP_200_OK: ChecklistReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        checklist_id,
    ):
        checklist = _get_visible_checklist(
            user=request.user,
            checklist_id=checklist_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = PositionSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            checklist = move_checklist(
                checklist=checklist,
                position=serializer.validated_data[
                    "position"
                ],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = ChecklistReadSerializer(
            checklist,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


class ChecklistItemCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChecklistItemCreateSerializer,
        responses={
            status.HTTP_201_CREATED: ChecklistItemReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        checklist_id,
    ):
        checklist = _get_visible_checklist(
            user=request.user,
            checklist_id=checklist_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = ChecklistItemCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            item = create_checklist_item(
                checklist=checklist,
                title=serializer.validated_data[
                    "title"
                ],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = ChecklistItemReadSerializer(
            item,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ChecklistItemDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChecklistItemUpdateSerializer,
        responses={
            status.HTTP_200_OK: ChecklistItemReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def patch(
        self,
        request,
        item_id,
    ):
        item = _get_visible_checklist_item(
            user=request.user,
            item_id=item_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            item.checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = ChecklistItemUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            item = update_checklist_item(
                item=item,
                **serializer.validated_data,
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = (
            ChecklistItemReadSerializer(
                item,
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def delete(
        self,
        request,
        item_id,
    ):
        item = _get_visible_checklist_item(
            user=request.user,
            item_id=item_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            item.checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        delete_checklist_item(
            item=item,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class ChecklistItemMoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PositionSerializer,
        responses={
            status.HTTP_200_OK: ChecklistItemReadSerializer
        },
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
    )
    def post(
        self,
        request,
        item_id,
    ):
        item = _get_visible_checklist_item(
            user=request.user,
            item_id=item_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            item.checklist.card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = PositionSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            item = move_checklist_item(
                item=item,
                position=serializer.validated_data[
                    "position"
                ],
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = (
            ChecklistItemReadSerializer(
                item,
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
                phone_number=serializer.validated_data[
                    "phone_number"
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
        description="Collaboration endpoint for managing labels, card labels, checklists, comments, and card assignees. Required permissions and request fields are defined in the schema.",
        tags=["Collaboration"],
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
