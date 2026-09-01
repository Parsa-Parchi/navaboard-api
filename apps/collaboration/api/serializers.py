from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.collaboration.models import (
    CardAssignee,
    CardLabel,
    Comment,
    Label,
    Checklist,
    ChecklistItem,
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
    phone_number = serializers.CharField()

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

class ChecklistItemReadSerializer(
    serializers.ModelSerializer
):
    checklist_id = serializers.UUIDField(
        read_only=True,
    )

    class Meta:
        model = ChecklistItem
        fields = (
            "id",
            "checklist_id",
            "title",
            "is_completed",
            "position",
            "created_at",
            "updated_at",
        )


class ChecklistReadSerializer(
    serializers.ModelSerializer
):
    card_id = serializers.UUIDField(
        read_only=True,
    )

    items = ChecklistItemReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Checklist
        fields = (
            "id",
            "card_id",
            "title",
            "position",
            "items",
            "created_at",
            "updated_at",
        )


class ChecklistCreateSerializer(
    serializers.Serializer
):
    title = serializers.CharField(
        max_length=120,
    )

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Checklist title is required."
            )

        return value


class ChecklistUpdateSerializer(
    ChecklistCreateSerializer
):
    pass


class PositionSerializer(serializers.Serializer):
    position = serializers.IntegerField(
        min_value=0,
    )


class ChecklistItemCreateSerializer(
    serializers.Serializer
):
    title = serializers.CharField(
        max_length=200,
    )

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Checklist item title is required."
            )

        return value


class ChecklistItemUpdateSerializer(
    serializers.Serializer
):
    title = serializers.CharField(
        max_length=200,
        required=False,
    )

    is_completed = serializers.BooleanField(
        required=False,
    )

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Checklist item title is required."
            )

        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        return attrs