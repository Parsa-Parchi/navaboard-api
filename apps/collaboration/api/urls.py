from django.urls import path

from apps.collaboration.api.views import (
    CardAssigneeDetailAPIView,
    CardAssigneeListCreateAPIView,
    CommentDetailAPIView,
    CommentListCreateAPIView,

    BoardLabelDetailAPIView,
    BoardLabelListCreateAPIView,
    CardLabelCreateAPIView,
    CardLabelDetailAPIView,
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
    path(
        "boards/<uuid:board_id>/labels/",
        BoardLabelListCreateAPIView.as_view(),
        name="board-label-list",
    ),
    path(
        "boards/<uuid:board_id>/labels/<uuid:label_id>/",
        BoardLabelDetailAPIView.as_view(),
        name="board-label-detail",
    ),
    path(
        "cards/<uuid:card_id>/labels/",
        CardLabelCreateAPIView.as_view(),
        name="card-label-create",
    ),
    path(
        "cards/<uuid:card_id>/labels/<uuid:label_id>/",
        CardLabelDetailAPIView.as_view(),
        name="card-label-detail",
    ),
]