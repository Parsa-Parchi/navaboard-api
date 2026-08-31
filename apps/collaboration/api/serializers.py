from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.collaboration.models import (
    CardAssignee,
    CardLabel,
    Comment,
    Label,
)


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

class LabelReadSerializer(serializers.ModelSerializer):
    board_id = serializers.UUIDField(
        read_only=True,
    )

    class Meta:
        model = Label
        fields = (
            "id",
            "board_id",
            "name",
            "color",
            "created_at",
            "updated_at",
        )


class LabelCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=80,
    )
    color = serializers.CharField(
        max_length=32,
    )

    def validate_name(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Label name is required."
            )

        return value

    def validate_color(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Label color is required."
            )

        return value


class LabelUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=80,
        required=False,
    )

    color = serializers.CharField(
        max_length=32,
        required=False,
    )

    def validate_name(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Label name is required."
            )

        return value

    def validate_color(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Label color is required."
            )

        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        return attrs


class CardLabelCreateSerializer(serializers.Serializer):
    label_id = serializers.UUIDField()


class CardLabelReadSerializer(serializers.ModelSerializer):
    card_id = serializers.UUIDField(
        read_only=True,
    )

    label = LabelReadSerializer(
        read_only=True,
    )

    class Meta:
        model = CardLabel
        fields = (
            "id",
            "card_id",
            "label",
        )