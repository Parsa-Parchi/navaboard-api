from rest_framework import serializers

from apps.boards.models import Board, BoardMembership
from apps.workspaces.models import WorkspaceMembership


class BoardReadSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    created_by = serializers.UUIDField(
        source="created_by_id",
        read_only=True,
        allow_null=True,
    )
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Board
        fields = (
            "id",
            "workspace_id",
            "name",
            "description",
            "visibility",
            "created_by",
            "current_user_role",
            "created_at",
            "updated_at",
        )

    def get_current_user_role(self, obj: Board) -> str | None:
        prefetched_workspace_memberships = getattr(
            obj.workspace,
            "current_user_memberships",
            None,
        )

        if prefetched_workspace_memberships is not None:
            workspace_role = (
                prefetched_workspace_memberships[0].role
                if prefetched_workspace_memberships
                else None
            )
        else:
            request = self.context.get("request")

            if request is None or not request.user.is_authenticated:
                return None

            workspace_role = obj.workspace.memberships.filter(
                user=request.user,
            ).values_list(
                "role",
                flat=True,
            ).first()

        if workspace_role == WorkspaceMembership.Role.OWNER:
            return BoardMembership.Role.ADMIN

        prefetched_board_memberships = getattr(
            obj,
            "current_user_board_memberships",
            None,
        )

        if prefetched_board_memberships is not None:
            return (
                prefetched_board_memberships[0].role
                if prefetched_board_memberships
                else None
            )

        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return None

        return obj.memberships.filter(
            workspace_membership__user=request.user,
        ).values_list(
            "role",
            flat=True,
        ).first()


class BoardWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = (
            "name",
            "description",
            "visibility",
        )

    def validate_name(self, value: str) -> str:
        normalized_name = value.strip()

        if not normalized_name:
            raise serializers.ValidationError(
                "Board name is required."
            )

        return normalized_name

    def validate_description(self, value: str) -> str:
        return value.strip()