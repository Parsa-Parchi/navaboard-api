from django.urls import path

from apps.workspaces.api.views import (
    WorkspaceDetailAPIView,
    WorkspaceListCreateAPIView,
    WorkspaceMembershipDetailAPIView,
    WorkspaceMembershipListCreateAPIView,
    WorkspaceOwnershipTransferAPIView,
)


app_name = "workspaces-api"

urlpatterns = [
    path(
        "",
        WorkspaceListCreateAPIView.as_view(),
        name="workspace-list",
    ),
    path(
        "<uuid:workspace_id>/",
        WorkspaceDetailAPIView.as_view(),
        name="workspace-detail",
    ),
    path(
        "<uuid:workspace_id>/members/",
        WorkspaceMembershipListCreateAPIView.as_view(),
        name="membership-list",
    ),
    path(
        "<uuid:workspace_id>/members/<uuid:membership_id>/",
        WorkspaceMembershipDetailAPIView.as_view(),
        name="membership-detail",
    ),
    path(
        "<uuid:workspace_id>/transfer-ownership/",
        WorkspaceOwnershipTransferAPIView.as_view(),
        name="transfer-ownership",
    ),
]

