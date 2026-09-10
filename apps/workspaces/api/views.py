from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.activity.mixins import ActivityMutationMixin

from apps.workspaces.api.permissions import (
    IsWorkspaceAdmin,
    IsWorkspaceMember,
    IsWorkspaceOwner,
)
from apps.workspaces.api.serializers import (
    WorkspaceMemberCreateSerializer,
    WorkspaceMembershipReadSerializer,
    WorkspaceMemberRoleUpdateSerializer,
    WorkspaceOwnershipTransferSerializer,
    WorkspaceReadSerializer,
    WorkspaceWriteSerializer,
)
from apps.workspaces.models import Workspace, WorkspaceMembership
from apps.workspaces.services.memberships import (
    add_workspace_member,
    change_workspace_member_role,
    remove_workspace_member,
)
from apps.workspaces.services.workspaces import (
    create_workspace,
    transfer_workspace_ownership,
)


User = get_user_model()


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _workspace_queryset_for_user(user):
    current_memberships = WorkspaceMembership.objects.filter(user=user)
    return (
        Workspace.objects.filter(memberships__user=user)
        .select_related("created_by")
        .prefetch_related(
            Prefetch(
                "memberships",
                queryset=current_memberships,
                to_attr="current_user_memberships",
            )
        )
        .distinct()
    )


def _get_visible_workspace(*, user, workspace_id) -> Workspace:
    return get_object_or_404(
        _workspace_queryset_for_user(user),
        pk=workspace_id,
    )


def _get_active_user(*, phone_number):
    try:
        return User.objects.get(
            phone_number=phone_number,
            is_active=True,
        )
    except User.DoesNotExist as exc:
        raise ValidationError(
            {
                "phone_number": "An active user with this phone number was not found."
            }
        ) from exc

class WorkspaceListCreateAPIView(ActivityMutationMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={status.HTTP_200_OK: WorkspaceReadSerializer(many=True)},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def get(self, request):
        workspaces = _workspace_queryset_for_user(request.user)
        serializer = WorkspaceReadSerializer(
            workspaces,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=WorkspaceWriteSerializer,
        responses={status.HTTP_201_CREATED: WorkspaceReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def post(self, request):
        serializer = WorkspaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            workspace = create_workspace(
                creator=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        response_serializer = WorkspaceReadSerializer(
            workspace,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceDetailAPIView(ActivityMutationMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Workspaces"], summary="Delete workspace", responses={204: None})
    def delete(self, request, workspace_id):
        workspace = self.get_object(request, workspace_id)
        if not IsWorkspaceOwner().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceOwner.message)
        workspace.delete()
        return Response(status=204)

    def get_object(self, request, workspace_id) -> Workspace:
        workspace = _get_visible_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )
        if not IsWorkspaceMember().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceMember.message)
        return workspace

    @extend_schema(
        responses={status.HTTP_200_OK: WorkspaceReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def get(self, request, workspace_id):
        workspace = self.get_object(request, workspace_id)
        serializer = WorkspaceReadSerializer(
            workspace,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=WorkspaceWriteSerializer,
        responses={status.HTTP_200_OK: WorkspaceReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def patch(self, request, workspace_id):
        workspace = self.get_object(request, workspace_id)
        if not IsWorkspaceAdmin().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceAdmin.message)

        serializer = WorkspaceWriteSerializer(
            workspace,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = WorkspaceReadSerializer(
            workspace,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class WorkspaceMembershipListCreateAPIView(ActivityMutationMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_workspace(self, request, workspace_id) -> Workspace:
        workspace = _get_visible_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )
        if not IsWorkspaceMember().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceMember.message)
        return workspace

    @extend_schema(
        responses={status.HTTP_200_OK: WorkspaceMembershipReadSerializer(many=True)},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def get(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id)
        memberships = workspace.memberships.select_related("user")
        serializer = WorkspaceMembershipReadSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=WorkspaceMemberCreateSerializer,
        responses={status.HTTP_201_CREATED: WorkspaceMembershipReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def post(self, request, workspace_id):
        workspace = self.get_workspace(request, workspace_id)
        if not IsWorkspaceAdmin().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceAdmin.message)

        serializer = WorkspaceMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        acting_membership = workspace.current_user_memberships[0]

        if (
            acting_membership.role == WorkspaceMembership.Role.ADMIN
            and role != WorkspaceMembership.Role.MEMBER
        ):
            raise PermissionDenied("Administrators may only add regular members.")

        user = _get_active_user(
            phone_number=serializer.validated_data["phone_number"]
        )


        try:
            membership = add_workspace_member(
                workspace=workspace,
                user=user,
                role=role,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        membership = WorkspaceMembership.objects.select_related("user").get(
            pk=membership.pk
        )
        response_serializer = WorkspaceMembershipReadSerializer(membership)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class WorkspaceMembershipDetailAPIView(ActivityMutationMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_objects(self, request, workspace_id, membership_id):
        workspace = _get_visible_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )
        membership = get_object_or_404(
            workspace.memberships.select_related("user"),
            pk=membership_id,
        )
        return workspace, membership

    @extend_schema(
        request=WorkspaceMemberRoleUpdateSerializer,
        responses={status.HTTP_200_OK: WorkspaceMembershipReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def patch(self, request, workspace_id, membership_id):
        workspace, membership = self.get_objects(
            request,
            workspace_id,
            membership_id,
        )
        if not IsWorkspaceOwner().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceOwner.message)

        serializer = WorkspaceMemberRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = change_workspace_member_role(
                membership=membership,
                role=serializer.validated_data["role"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        membership = WorkspaceMembership.objects.select_related("user").get(
            pk=membership.pk
        )
        response_serializer = WorkspaceMembershipReadSerializer(membership)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={status.HTTP_204_NO_CONTENT: None},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def delete(self, request, workspace_id, membership_id):
        workspace, membership = self.get_objects(
            request,
            workspace_id,
            membership_id,
        )
        acting_membership = workspace.current_user_memberships[0]
        removing_self = membership.user_id == request.user.id
        can_remove_other = (
            acting_membership.role == WorkspaceMembership.Role.OWNER
            or (
                acting_membership.role == WorkspaceMembership.Role.ADMIN
                and membership.role == WorkspaceMembership.Role.MEMBER
            )
        )

        if not removing_self and not can_remove_other:
            raise PermissionDenied("You cannot remove this workspace member.")

        try:
            remove_workspace_member(membership=membership)
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceOwnershipTransferAPIView(ActivityMutationMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=WorkspaceOwnershipTransferSerializer,
        responses={status.HTTP_200_OK: WorkspaceMembershipReadSerializer},
        summary="Workspace API operation",
        description="Workspace management endpoint. Handles workspace data, members, roles, and ownership operations. Check request and response schemas for required fields.",
        tags=["Workspaces"],
    )
    def post(self, request, workspace_id):
        workspace = _get_visible_workspace(
            user=request.user,
            workspace_id=workspace_id,
        )
        if not IsWorkspaceOwner().has_object_permission(request, self, workspace):
            raise PermissionDenied(IsWorkspaceOwner.message)

        serializer = WorkspaceOwnershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_owner = _get_active_user(
            phone_number=serializer.validated_data["new_owner_phone_number"]
        )


        try:
            membership = transfer_workspace_ownership(
                workspace=workspace,
                acting_user=request.user,
                new_owner=new_owner,
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)

        membership = WorkspaceMembership.objects.select_related("user").get(
            pk=membership.pk
        )
        response_serializer = WorkspaceMembershipReadSerializer(membership)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
