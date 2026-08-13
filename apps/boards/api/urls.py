from django.urls import path

from apps.boards.api.views import (
    BoardDetailAPIView,
    BoardListCreateAPIView,
    BoardListDetailAPIView,
    BoardListListCreateAPIView,
    BoardListMoveAPIView,
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
    path(
        "boards/<uuid:board_id>/lists/",
        BoardListListCreateAPIView.as_view(),
        name="list-list",
    ),
    path(
        "boards/<uuid:board_id>/lists/<uuid:list_id>/",
        BoardListDetailAPIView.as_view(),
        name="list-detail",
    ),
    path(
        "boards/<uuid:board_id>/lists/<uuid:list_id>/move/",
        BoardListMoveAPIView.as_view(),
        name="list-move",
    ),
]