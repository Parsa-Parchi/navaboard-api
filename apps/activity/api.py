from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import generics, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.api.views import _get_visible_board
from apps.collaboration.api.views import _get_visible_card
from apps.workspaces.api.views import _get_visible_workspace
from .models import Activity, Notification
from .services import visible_activities


class FeedPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ("id", "workspace", "board", "card", "actor", "action", "resource_id", "created_at")
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "activity", "read_at", "created_at")
        read_only_fields = fields


@extend_schema(tags=["Activity"], summary="Read workspace, board or card activity", description="Newest first, paginated. Only currently accessible workspace/board events are returned. History is read-only. action identifies the API route and HTTP method; resource_id identifies the affected object.")
class ActivityList(generics.ListAPIView):
    serializer_class = ActivitySerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Activity.objects.none()
        query = visible_activities(self.request.user)
        if "workspace_id" in self.kwargs:
            workspace = _get_visible_workspace(user=self.request.user, workspace_id=self.kwargs["workspace_id"])
            query = query.filter(workspace=workspace)
        if "board_id" in self.kwargs:
            board = _get_visible_board(user=self.request.user, board_id=self.kwargs["board_id"])
            query = query.filter(board=board)
        if "card_id" in self.kwargs:
            card = _get_visible_card(user=self.request.user, card_id=self.kwargs["card_id"])
            query = query.filter(card=card)
        return query


def notification_queryset(user):
    return Notification.objects.filter(recipient=user, activity__in=visible_activities(user)).select_related("activity")


@extend_schema(tags=["Notifications"], summary="List your notifications", description="Persistent in-app inbox, newest first. Poll this endpoint; notifications are generated for card assignees/creator and membership changes, excluding your own actions. Access is rechecked on every read.", parameters=[OpenApiParameter("unread", bool, description="true: unread only; false: read only; omit: all.")])
class NotificationList(generics.ListAPIView):
    serializer_class = NotificationSerializer
    pagination_class = FeedPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        query = notification_queryset(self.request.user)
        unread = self.request.query_params.get("unread")
        if unread is not None:
            if unread not in {"true", "false"}:
                raise serializers.ValidationError({"unread": "Use true or false."})
            query = query.filter(read_at__isnull=unread == "true")
        return query


class NotificationRead(APIView):
    @extend_schema(tags=["Notifications"], summary="Mark one notification read", description="Idempotent. Other users' notifications return 404.", request=None, responses=NotificationSerializer)
    def post(self, request, notification_id):
        item = get_object_or_404(notification_queryset(request.user), pk=notification_id)
        Notification.objects.filter(pk=item.pk, read_at__isnull=True).update(read_at=timezone.now())
        item.refresh_from_db()
        return Response(NotificationSerializer(item).data)


class NotificationReadAll(APIView):
    @extend_schema(tags=["Notifications"], summary="Mark all accessible notifications read", description="Returns the number newly marked read. Idempotent.", request=None, responses=inline_serializer("NotificationReadAllResponse", fields={"updated": serializers.IntegerField()}))
    def post(self, request):
        count = notification_queryset(request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": count})


class NotificationCount(APIView):
    @extend_schema(tags=["Notifications"], summary="Get unread notification count", description="Use for the inbox badge; excludes inaccessible events.", responses=inline_serializer("NotificationCountResponse", fields={"count": serializers.IntegerField()}))
    def get(self, request):
        return Response({"count": notification_queryset(request.user).filter(read_at__isnull=True).count()})


urlpatterns = [
    path("workspaces/<uuid:workspace_id>/activity/", ActivityList.as_view(), name="workspace-activity"),
    path("boards/<uuid:board_id>/activity/", ActivityList.as_view(), name="board-activity"),
    path("cards/<uuid:card_id>/activity/", ActivityList.as_view(), name="card-activity"),
    path("notifications/", NotificationList.as_view(), name="notification-list"),
    path("notifications/unread-count/", NotificationCount.as_view(), name="notification-count"),
    path("notifications/read-all/", NotificationReadAll.as_view(), name="notification-read-all"),
    path("notifications/<uuid:notification_id>/read/", NotificationRead.as_view(), name="notification-read"),
]
