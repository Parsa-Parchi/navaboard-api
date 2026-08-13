from django.urls import path

from apps.boards.api.views import (
    BoardDetailAPIView,
    BoardListCreateAPIView,
    BoardMembershipDetailAPIView,
    BoardMembershipListCreateAPIView,
)


app_name = "boards-api"


urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/boards/",
        BoardListCreateAPIView.as_view(),
        name="board-list",
    ),
    path(
        "boards/<uuid:board_id>/",
        BoardDetailAPIView.as_view(),
        name="board-detail",
    ),
    path(
        "boards/<uuid:board_id>/members/",
        BoardMembershipListCreateAPIView.as_view(),
        name="membership-list",
    ),
    path(
        "boards/<uuid:board_id>/members/<uuid:membership_id>/",
        BoardMembershipDetailAPIView.as_view(),
        name="membership-detail",
    ),
]