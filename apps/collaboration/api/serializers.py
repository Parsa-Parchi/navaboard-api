from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.collaboration.models import CardAssignee, Comment


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

class CommentAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
        )


class CommentReadSerializer(serializers.ModelSerializer):
    card_id = serializers.UUIDField(
        read_only=True,
    )

    author = CommentAuthorSerializer(
        read_only=True,
    )

    class Meta:
        model = Comment
        fields = (
            "id",
            "card_id",
            "author",
            "body",
            "created_at",
            "updated_at",
        )


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        body = value.strip()

        if not body:
            raise serializers.ValidationError(
                "Comment body is required."
            )

        return body


class CommentUpdateSerializer(serializers.Serializer):
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        body = value.strip()

        if not body:
            raise serializers.ValidationError(
                "Comment body is required."
            )

        return body