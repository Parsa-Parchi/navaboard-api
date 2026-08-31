from django.urls import path

from apps.collaboration.api.views import (
    CardAssigneeDetailAPIView,
    CardAssigneeListCreateAPIView,
    CommentDetailAPIView,
    CommentListCreateAPIView,
)


app_name = "collaboration-api"


urlpatterns = [
    path(
        "cards/<uuid:card_id>/members/",
        CardAssigneeListCreateAPIView.as_view(),
        name="card-assignee-list",
    ),
    path(
        "cards/<uuid:card_id>/members/<uuid:assignee_id>/",
        CardAssigneeDetailAPIView.as_view(),
        name="card-assignee-detail",
    ),

    path(
        "cards/<uuid:card_id>/comments/",
        CommentListCreateAPIView.as_view(),
        name="comment-list",
    ),
    path(
        "comments/<uuid:comment_id>/",
        CommentDetailAPIView.as_view(),
        name="comment-detail",
    ),
]