from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class WorkspaceReadSerializer(serializers.ModelSerializer):
    created_by = serializers.UUIDField(
        source="created_by_id",
        read_only=True,
        allow_null=True,
    )
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            "id",
            "name",
            "description",
            "created_by",
            "current_user_role",
            "created_at",
            "updated_at",
        )

    def get_current_user_role(self, obj: Workspace) -> str | None:
        prefetched_memberships = getattr(obj, "current_user_memberships", None)
        if prefetched_memberships is not None:
            return prefetched_memberships[0].role if prefetched_memberships else None

        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None

        return obj.memberships.filter(user=request.user).values_list(
            "role",
            flat=True,
        ).first()


class WorkspaceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ("name", "description")

    def validate_name(self, value: str) -> str:
        normalized_name = value.strip()
        if not normalized_name:
            raise serializers.ValidationError("Workspace name is required.")
        return normalized_name

    def validate_description(self, value: str) -> str:
        return value.strip()


class WorkspaceMemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "full_name")


class WorkspaceMembershipReadSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(read_only=True)
    user = WorkspaceMemberUserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = (
            "id",
            "workspace_id",
            "user",
            "role",
            "joined_at",
        )


class WorkspaceMemberCreateSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    role = serializers.ChoiceField(
        choices=(
            WorkspaceMembership.Role.ADMIN,
            WorkspaceMembership.Role.MEMBER,
        ),
        default=WorkspaceMembership.Role.MEMBER,
    )


class WorkspaceMemberRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=(
            WorkspaceMembership.Role.ADMIN,
            WorkspaceMembership.Role.MEMBER,
        ),
    )


class WorkspaceOwnershipTransferSerializer(serializers.Serializer):
    new_owner_phone_number = serializers.CharField()

