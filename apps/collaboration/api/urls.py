from django.urls import path

from apps.collaboration.api.views import (
    CardAssigneeDetailAPIView,
    CardAssigneeListCreateAPIView,
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
]