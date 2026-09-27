from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers

from apps.activity.api import FeedPagination
from apps.boards.api.serializers import CardReadSerializer, BoardReadSerializer
from apps.boards.api.filters import CardSearchParameters, filter_cards
from apps.boards.api.views import _board_queryset_for_user
from apps.collaboration.api.views import _card_queryset_for_user
from apps.core.search import TextSearchParameters, filter_named_resources


class BoardSearchParameters(TextSearchParameters):
    workspace_id = serializers.UUIDField(required=False)


class CardSearchReadSerializer(CardReadSerializer):
    board_id = serializers.UUIDField(source="board_list.board_id", read_only=True)
    board_name = serializers.CharField(source="board_list.board.name", read_only=True)
    workspace_id = serializers.UUIDField(source="board_list.board.workspace_id", read_only=True)
    list_title = serializers.CharField(source="board_list.title", read_only=True)

    class Meta(CardReadSerializer.Meta):
        fields = CardReadSerializer.Meta.fields + ("board_id", "board_name", "workspace_id", "list_title")


@extend_schema(tags=["Cards"], summary="Search your accessible cards", description="Paginated newest-first search. All words/operators and filter groups combine with AND; member_ids and label_ids each match any selected value. Quoted phrases and negative terms are supported. Only accessible active cards and active related content are searched. Use board_id to scope to a board, or filter the hydrated board endpoint to preserve columns. Dates are ISO 8601 with timezone. Unsupported operators and malformed filters return 400; traffic limits return 429 with Retry-After.", parameters=[CardSearchParameters])
class CardSearch(generics.ListAPIView):
    is_search_view = True
    serializer_class = CardSearchReadSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            from apps.boards.models import Card
            return Card.objects.none()
        parameters = CardSearchParameters(data=self.request.query_params)
        parameters.is_valid(raise_exception=True)
        values = parameters.validated_data
        query = filter_cards(_card_queryset_for_user(self.request.user), values, self.request.user)
        return query.order_by("-created_at", "-id").distinct()


@extend_schema(tags=["Boards"], summary="Search boards across your workspaces", description="Paginated boards visible to the current user, newest first. q is a literal case-insensitive substring of name or description. Optional workspace_id narrows the search. Private boards require board membership or workspace ownership; deleted workspaces and boards are excluded. Empty q lists accessible boards. Rate limits return 429 and Retry-After.", parameters=[BoardSearchParameters])
class BoardSearch(generics.ListAPIView):
    is_search_view = True
    serializer_class = BoardReadSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            from apps.boards.models import Board
            return Board.objects.none()
        parameters = BoardSearchParameters(data=self.request.query_params)
        parameters.is_valid(raise_exception=True)
        query = filter_named_resources(_board_queryset_for_user(self.request.user), self.request.query_params)
        if "workspace_id" in parameters.validated_data:
            query = query.filter(workspace_id=parameters.validated_data["workspace_id"])
        return query.order_by("-created_at", "-id")


urlpatterns = [path("cards/", CardSearch.as_view(), name="card-search"),
               path("boards/", BoardSearch.as_view(), name="board-search")]
