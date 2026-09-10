from django.db.models import Q
from django.urls import path
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, serializers

from apps.activity.api import FeedPagination
from apps.boards.api.serializers import CardReadSerializer
from apps.collaboration.api.views import _card_queryset_for_user


class CardSearchParameters(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=200, allow_blank=True)
    workspace_id = serializers.UUIDField(required=False)
    board_id = serializers.UUIDField(required=False)
    assigned_to_me = serializers.BooleanField(required=False)
    due_before = serializers.DateTimeField(required=False)
    due_after = serializers.DateTimeField(required=False)


@extend_schema(tags=["Cards"], summary="Search your accessible cards", description="Paginated newest-first search over card title/description. Combines all supplied filters. Private, deleted and inaccessible board/list/workspace contents are excluded. Dates are ISO 8601 with timezone.", parameters=[CardSearchParameters])
class CardSearch(generics.ListAPIView):
    serializer_class = CardReadSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            from apps.boards.models import Card
            return Card.objects.none()
        parameters = CardSearchParameters(data=self.request.query_params)
        parameters.is_valid(raise_exception=True)
        values = parameters.validated_data
        query = _card_queryset_for_user(self.request.user)
        if values.get("q"):
            query = query.filter(Q(title__icontains=values["q"]) | Q(description__icontains=values["q"]))
        for name, lookup in {
            "workspace_id": "board_list__board__workspace_id",
            "board_id": "board_list__board_id",
            "due_before": "due_at__lte",
            "due_after": "due_at__gte",
        }.items():
            if name in values:
                query = query.filter(**{lookup: values[name]})
        if "assigned_to_me" in values:
            lookup = {"assignees__workspace_membership__user": self.request.user}
            query = query.filter(**lookup) if values["assigned_to_me"] else query.exclude(**lookup)
        return query.order_by("-created_at", "-id").distinct()


urlpatterns = [path("cards/", CardSearch.as_view(), name="card-search")]
