from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.api.permissions import (
    CanViewBoard,
    IsBoardAdmin,
)
from apps.boards.api.serializers import (
    BoardReadSerializer,
    BoardWriteSerializer,
)
from apps.boards.models import Board, BoardMembership
from apps.boards.services.boards import create_board
from apps.workspaces.models import (
    Workspace,
    WorkspaceMembership,
)


def _raise_api_validation_error(
    exc: DjangoValidationError,
) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc

    raise ValidationError(exc.messages) from exc


def _board_queryset_for_user(user):
    current_workspace_memberships = (
        WorkspaceMembership.objects.filter(
            user=user,
        )
    )

    current_board_memberships = (
        BoardMembership.objects.filter(
            workspace_membership__user=user,
        ).select_related(
            "workspace_membership",
        )
    )

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
            "created_by",
        )
        .prefetch_related(
            Prefetch(
                "workspace__memberships",
                queryset=current_workspace_memberships,
                to_attr="current_user_memberships",
            ),
            Prefetch(
                "memberships",
                queryset=current_board_memberships,
                to_attr="current_user_board_memberships",
            ),
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


def _get_member_workspace(
    *,
    user,
    workspace_id,
) -> Workspace:
    return get_object_or_404(
        Workspace.objects.filter(
            memberships__user=user,
        ).distinct(),
        pk=workspace_id,
    )


class BoardListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            status.HTTP_200_OK: BoardReadSerializer(
                many=True
            )
        },
        tags=["boards"],
    )
    def get(self, request, workspace_id):
        workspace = _get_member_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )

        boards = _board_queryset_for_user(
            request.user
        ).filter(
            workspace=workspace,
        )

        serializer = BoardReadSerializer(
            boards,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoardWriteSerializer,
        responses={
            status.HTTP_201_CREATED: BoardReadSerializer
        },
        tags=["boards"],
    )
    def post(self, request, workspace_id):
        workspace = _get_member_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )

        serializer = BoardWriteSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        try:
            board = create_board(
                workspace=workspace,
                creator=request.user,
                **serializer.validated_data,
            )

        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = BoardReadSerializer(
            board,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class BoardDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(
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
            status.HTTP_200_OK: BoardReadSerializer
        },
        tags=["boards"],
    )
    def get(
        self,
        request,
        board_id,
    ):
        board = self.get_object(
            request,
            board_id,
        )

        serializer = BoardReadSerializer(
            board,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoardWriteSerializer,
        responses={
            status.HTTP_200_OK: BoardReadSerializer
        },
        tags=["boards"],
    )
    def patch(
        self,
        request,
        board_id,
    ):
        board = self.get_object(
            request,
            board_id,
        )

        if not IsBoardAdmin().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                IsBoardAdmin.message
            )

        serializer = BoardWriteSerializer(
            board,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        serializer.save()

        response_serializer = BoardReadSerializer(
            board,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        tags=["boards"],
    )
    def delete(
        self,
        request,
        board_id,
    ):
        board = self.get_object(
            request,
            board_id,
        )

        if not IsBoardAdmin().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                IsBoardAdmin.message
            )

        board.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )