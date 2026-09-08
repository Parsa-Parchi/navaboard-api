from django.urls import path

from apps.boards.api.views import (
    BoardDetailAPIView,
    BoardListCreateAPIView,
    BoardListDetailAPIView,
    BoardListListCreateAPIView,
    BoardListMoveAPIView,
    BoardMembershipDetailAPIView,
    BoardMembershipListCreateAPIView,
    CardDetailAPIView,
    CardListCreateAPIView,
    CardMoveAPIView,
)


app_name = "boards-api"


urlpatterns = [

    # 1. Board List / Create
    path(
        "workspaces/<uuid:workspace_id>/boards/",
        BoardListCreateAPIView.as_view(),
        name="board-list",
    ),

    # 2. Board Detail (GET / PATCH / DELETE)
    path(
        "boards/<uuid:board_id>/",
        BoardDetailAPIView.as_view(),
        name="board-detail",
    ),


    # 3. Board Members List / Create
    path(
        "boards/<uuid:board_id>/members/",
        BoardMembershipListCreateAPIView.as_view(),
        name="membership-list",
    ),

    # 4. Board Member Detail (PATCH / DELETE)
    path(
        "boards/<uuid:board_id>/members/<uuid:membership_id>/",
        BoardMembershipDetailAPIView.as_view(),
        name="membership-detail",
    ),


    # 5. Board Lists List / Create
    path(
        "boards/<uuid:board_id>/lists/",
        BoardListListCreateAPIView.as_view(),
        name="list-list",
    ),

    # 6. Board List Detail (PATCH / DELETE)
    path(
        "boards/<uuid:board_id>/lists/<uuid:list_id>/",
        BoardListDetailAPIView.as_view(),
        name="list-detail",
    ),

    # 7. Board List Move
    path(
        "boards/<uuid:board_id>/lists/<uuid:list_id>/move/",
        BoardListMoveAPIView.as_view(),
        name="list-move",
    ),


    # 8. Cards List / Create
    path(
        "boards/<uuid:board_id>/lists/<uuid:list_id>/cards/",
        CardListCreateAPIView.as_view(),
        name="card-list",
    ),

    # 9. Card Detail (GET / PATCH / DELETE)
    path(
        "boards/<uuid:board_id>/cards/<uuid:card_id>/",
        CardDetailAPIView.as_view(),
        name="card-detail",
    ),

    # 10. Card Move
    path(
        "boards/<uuid:board_id>/cards/<uuid:card_id>/move/",
        CardMoveAPIView.as_view(),
        name="card-move",
    ),
]