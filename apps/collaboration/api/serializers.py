from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.collaboration.models import CardAssignee


User = get_user_model()


class CardAssigneeUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
        )


class CardAssigneeReadSerializer(serializers.ModelSerializer):
    card_id = serializers.UUIDField(
        read_only=True,
    )

    workspace_membership_id = serializers.UUIDField(
        read_only=True,
    )

    user = CardAssigneeUserSerializer(
        source="workspace_membership.user",
        read_only=True,
    )

    assigned_by = serializers.UUIDField(
        source="assigned_by_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = CardAssignee
        fields = (
            "id",
            "card_id",
            "workspace_membership_id",
            "user",
            "assigned_by",
            "assigned_at",
        )


class CardAssigneeCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()