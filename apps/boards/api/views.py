from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.api.permissions import (
    CanEditBoard,
    CanViewBoard,
    IsBoardAdmin,
)
from apps.boards.api.serializers import (
    BoardListCreateSerializer,
    BoardListMoveSerializer,
    BoardListReadSerializer,
    BoardListUpdateSerializer,
    BoardMemberCreateSerializer,
    BoardMembershipReadSerializer,
    BoardMemberRoleUpdateSerializer,
    BoardReadSerializer,
    BoardWriteSerializer,
    CardCreateSerializer,
    CardMoveSerializer,
    CardReadSerializer,
    CardUpdateSerializer,
    BoardDetailReadSerializer,
)
from apps.boards.models import (
    Board,
    BoardList,
    BoardMembership,
    Card,
)
from apps.boards.services.boards import (
    add_board_member,
    change_board_member_role,
    create_board,
    remove_board_member,
    delete_board,
)

from apps.boards.services.lists import (
    create_board_list,
    delete_board_list,
    move_board_list,
    update_board_list,
)
from apps.workspaces.models import (
    Workspace,
    WorkspaceMembership,
)

from apps.boards.services.cards import (
    create_card,
    delete_card,
    move_card,
    update_card,
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

def _get_visible_board_detail(
    *,
    user,
    board_id,
) -> Board:
    cards_queryset = (
        Card.objects.select_related(
            "created_by",
        ).order_by(
            "position",
            "created_at",
        )
    )

    lists_queryset = (
        BoardList.objects.order_by(
            "position",
            "created_at",
        ).prefetch_related(
            Prefetch(
                "cards",
                queryset=cards_queryset,
            )
        )
    )

    queryset = (
        _board_queryset_for_user(user)
        .prefetch_related(
            Prefetch(
                "lists",
                queryset=lists_queryset,
            )
        )
    )

    return get_object_or_404(
        queryset,
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


def _get_board_workspace_membership(
    *,
    board: Board,
    phone_number,
) -> WorkspaceMembership:
    try:
        return WorkspaceMembership.objects.select_related(
            "user",
        ).get(
            workspace=board.workspace,
            user__phone_number=phone_number,
            user__is_active=True,
        )
    except WorkspaceMembership.DoesNotExist as exc:
        raise ValidationError(
            {
                "user_id": (
                    "An active member of this board's workspace "
                    "with this id was not found."
                )
            }
        ) from exc






@extend_schema_view(
    get=extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="List boards in workspace",
    ),
    post=extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="Create board in workspace",
    ),
)
class BoardListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="List boards in workspace",
        responses={
            status.HTTP_200_OK: BoardReadSerializer(many=True)
        },
    )
    def get(
        self,
        request,
        workspace_id,
    ):
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
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="Create board in workspace",
        request=BoardWriteSerializer,
        responses={
            status.HTTP_201_CREATED: BoardReadSerializer
        },
    )
    def post(
        self,
        request,
        workspace_id,
    ):
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


@extend_schema_view(
    get=extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="Get board details",
    ),
    patch=extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="Update board",
    ),
    delete=extend_schema(
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
        summary="Delete board",
    ),
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
        summary="Get board details",
        responses={
            status.HTTP_200_OK: BoardDetailReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def get(
        self,
        request,
        board_id,
    ):
        board = _get_visible_board_detail(
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

        serializer = BoardDetailReadSerializer(
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
        summary="Update board",
        request=BoardWriteSerializer,
        responses={
            status.HTTP_200_OK: BoardReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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
        summary="Delete board",
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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

        delete_board(
            board=board,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
class BoardMembershipListCreateAPIView(APIView):
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
            status.HTTP_200_OK: BoardMembershipReadSerializer(
                many=True
            )
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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

        memberships = board.memberships.select_related(
            "workspace_membership__user",
        )

        serializer = BoardMembershipReadSerializer(
            memberships,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoardMemberCreateSerializer,
        responses={
            status.HTTP_201_CREATED: BoardMembershipReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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

        if not IsBoardAdmin().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                IsBoardAdmin.message
            )

        serializer = BoardMemberCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        workspace_membership = (
            _get_board_workspace_membership(
                board=board,
                phone_number=serializer.validated_data["phone_number"],
            )
        )

        try:
            membership = add_board_member(
                board=board,
                workspace_membership=workspace_membership,
                role=serializer.validated_data["role"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        membership = BoardMembership.objects.select_related(
            "workspace_membership__user",
        ).get(
            pk=membership.pk,
        )

        response_serializer = BoardMembershipReadSerializer(
            membership,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class BoardMembershipDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_objects(
        self,
        request,
        board_id,
        membership_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        membership = get_object_or_404(
            board.memberships.select_related(
                "workspace_membership__user",
            ),
            pk=membership_id,
        )

        return board, membership

    @extend_schema(
        request=BoardMemberRoleUpdateSerializer,
        responses={
            status.HTTP_200_OK: BoardMembershipReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def patch(
        self,
        request,
        board_id,
        membership_id,
    ):
        board, membership = self.get_objects(
            request,
            board_id,
            membership_id,
        )

        if not IsBoardAdmin().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                IsBoardAdmin.message
            )

        serializer = BoardMemberRoleUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        try:
            membership = change_board_member_role(
                membership=membership,
                role=serializer.validated_data["role"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        membership = BoardMembership.objects.select_related(
            "workspace_membership__user",
        ).get(
            pk=membership.pk,
        )

        response_serializer = BoardMembershipReadSerializer(
            membership,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def delete(
        self,
        request,
        board_id,
        membership_id,
    ):
        board, membership = self.get_objects(
            request,
            board_id,
            membership_id,
        )

        removing_self = (
            membership.user_id == request.user.id
        )

        if (
            not removing_self
            and not IsBoardAdmin().has_object_permission(
                request,
                self,
                board,
            )
        ):
            raise PermissionDenied(
                "You cannot remove this board member."
            )

        try:
            remove_board_member(
                membership=membership,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )




@extend_schema_view(
    get=extend_schema(
        description="Board list management endpoint. Handles creating, updating, deleting, and moving lists inside a board.",
        tags=["Board Lists"],
        summary="List board lists",
    ),
    post=extend_schema(
        description="Board list management endpoint. Handles creating, updating, deleting, and moving lists inside a board.",
        tags=["Board Lists"],
        summary="Create board list",
    ),
)
class BoardListListCreateAPIView(APIView):
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
            status.HTTP_200_OK: BoardListReadSerializer(
                many=True
            )
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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

        board_lists = board.lists.all()

        serializer = BoardListReadSerializer(
            board_lists,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoardListCreateSerializer,
        responses={
            status.HTTP_201_CREATED: BoardListReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
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

        if not CanEditBoard().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = BoardListCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            board_list = create_board_list(
                board=board,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = BoardListReadSerializer(
            board_list,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    patch=extend_schema(
        description="Board list management endpoint. Handles creating, updating, deleting, and moving lists inside a board.",
        tags=["Board Lists"],
        summary="Update board list",
    ),
    delete=extend_schema(
        description="Board list management endpoint. Handles creating, updating, deleting, and moving lists inside a board.",
        tags=["Board Lists"],
        summary="Delete board list",
    ),
)
class BoardListDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_objects(
        self,
        request,
        board_id,
        list_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        board_list = get_object_or_404(
            BoardList.objects.select_related(
                "board",
                "board__workspace",
            ),
            pk=list_id,
            board=board,
        )

        return board, board_list

    @extend_schema(
        request=BoardListUpdateSerializer,
        responses={
            status.HTTP_200_OK: BoardListReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def patch(
        self,
        request,
        board_id,
        list_id,
    ):
        board, board_list = self.get_objects(
            request,
            board_id,
            list_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            board_list,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = BoardListUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            board_list = update_board_list(
                board_list=board_list,
                title=serializer.validated_data["title"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = BoardListReadSerializer(
            board_list,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def delete(
        self,
        request,
        board_id,
        list_id,
    ):
        board, board_list = self.get_objects(
            request,
            board_id,
            list_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            board_list,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        delete_board_list(
            board_list=board_list,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


@extend_schema_view(
    post=extend_schema(
        description="Board list management endpoint. Handles creating, updating, deleting, and moving lists inside a board.",
        tags=["Board Lists"],
        summary="Move board list",
    ),
)
class BoardListMoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BoardListMoveSerializer,
        responses={
            status.HTTP_200_OK: BoardListReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def post(
        self,
        request,
        board_id,
        list_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        board_list = get_object_or_404(
            BoardList.objects.select_related(
                "board",
                "board__workspace",
            ),
            pk=list_id,
            board=board,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            board_list,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = BoardListMoveSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            board_list = move_board_list(
                board_list=board_list,
                position=serializer.validated_data["position"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = BoardListReadSerializer(
            board_list,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

@extend_schema_view(
    get=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="List cards in board list",
    ),
    post=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="Create card in board list",
    ),
)
class CardListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_objects(
        self,
        request,
        board_id,
        list_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        board_list = get_object_or_404(
            BoardList.objects.select_related(
                "board",
                "board__workspace",
            ),
            pk=list_id,
            board=board,
        )

        return board, board_list

    @extend_schema(
        responses={
            status.HTTP_200_OK: CardReadSerializer(
                many=True
            )
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def get(
        self,
        request,
        board_id,
        list_id,
    ):
        board, board_list = self.get_objects(
            request,
            board_id,
            list_id,
        )

        if not CanViewBoard().has_object_permission(
            request,
            self,
            board,
        ):
            raise PermissionDenied(
                CanViewBoard.message
            )

        cards = board_list.cards.select_related(
            "created_by",
        ).all()

        serializer = CardReadSerializer(
            cards,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CardCreateSerializer,
        responses={
            status.HTTP_201_CREATED: CardReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def post(
        self,
        request,
        board_id,
        list_id,
    ):
        board, board_list = self.get_objects(
            request,
            board_id,
            list_id,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            board_list,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = CardCreateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            card = create_card(
                board_list=board_list,
                creator=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = CardReadSerializer(
            card,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="Get card details",
    ),
    patch=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="Update card",
    ),
    delete=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="Delete card",
    ),
)
class CardDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_objects(
        self,
        request,
        board_id,
        card_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        card = get_object_or_404(
            Card.objects.select_related(
                "board_list",
                "board_list__board",
                "board_list__board__workspace",
                "created_by",
            ),
            pk=card_id,
            board_list__board=board,
        )

        return board, card

    @extend_schema(
        responses={
            status.HTTP_200_OK: CardReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def get(
        self,
        request,
        board_id,
        card_id,
    ):
        board, card = self.get_objects(
            request,
            board_id,
            card_id,
        )

        if not CanViewBoard().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanViewBoard.message
            )

        serializer = CardReadSerializer(
            card,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CardUpdateSerializer,
        responses={
            status.HTTP_200_OK: CardReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def patch(
        self,
        request,
        board_id,
        card_id,
    ):
        board, card = self.get_objects(
            request,
            board_id,
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

        serializer = CardUpdateSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            card = update_card(
                card=card,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = CardReadSerializer(
            card,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def delete(
        self,
        request,
        board_id,
        card_id,
    ):
        board, card = self.get_objects(
            request,
            board_id,
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

        delete_card(
            card=card,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


@extend_schema_view(
    post=extend_schema(
        description="Card management endpoint. Handles card creation, retrieval, update, deletion, and movement between lists.",
        tags=["Cards"],
        summary="Move card",
    ),
)
class CardMoveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CardMoveSerializer,
        responses={
            status.HTTP_200_OK: CardReadSerializer
        },
        description="Board management endpoint. Handles boards, lists, cards, and membership operations. Required permissions and request fields are defined in the schema.",
        tags=["Boards"],
    )
    def post(
        self,
        request,
        board_id,
        card_id,
    ):
        board = _get_visible_board(
            user=request.user,
            board_id=board_id,
        )

        card = get_object_or_404(
            Card.objects.select_related(
                "board_list",
                "board_list__board",
                "board_list__board__workspace",
            ),
            pk=card_id,
            board_list__board=board,
        )

        if not CanEditBoard().has_object_permission(
            request,
            self,
            card,
        ):
            raise PermissionDenied(
                CanEditBoard.message
            )

        serializer = CardMoveSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        destination_list = BoardList.objects.filter(
            pk=serializer.validated_data[
                "destination_list_id"
            ],
            board=board,
        ).first()

        if destination_list is None:
            raise ValidationError(
                {
                    "destination_list_id": (
                        "Destination list must belong "
                        "to this board."
                    )
                }
            )

        try:
            card = move_card(
                card=card,
                destination_list=destination_list,
                position=serializer.validated_data[
                    "position"
                ],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        card = Card.objects.select_related(
            "board_list",
            "created_by",
        ).get(
            pk=card.pk,
        )

        response_serializer = CardReadSerializer(
            card,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )