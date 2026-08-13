from django.contrib.auth import get_user_model
from rest_framework import serializers


from apps.boards.models import (
    Board,
    BoardList,
    BoardMembership,
    Card,
)


from apps.workspaces.models import WorkspaceMembership


User = get_user_model()


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


class BoardMemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
        )


class BoardMembershipReadSerializer(serializers.ModelSerializer):
    board_id = serializers.UUIDField(read_only=True)
    workspace_membership_id = serializers.UUIDField(read_only=True)
    user = BoardMemberUserSerializer(
        source="workspace_membership.user",
        read_only=True,
    )

    class Meta:
        model = BoardMembership
        fields = (
            "id",
            "board_id",
            "workspace_membership_id",
            "user",
            "role",
            "joined_at",
        )


class BoardMemberCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(
        choices=(
            BoardMembership.Role.ADMIN,
            BoardMembership.Role.MEMBER,
        ),
        default=BoardMembership.Role.MEMBER,
    )


class BoardMemberRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=(
            BoardMembership.Role.ADMIN,
            BoardMembership.Role.MEMBER,
        ),
    )

class BoardListReadSerializer(serializers.ModelSerializer):
    board_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = BoardList
        fields = (
            "id",
            "board_id",
            "title",
            "position",
            "created_at",
            "updated_at",
        )


class BoardListCreateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=120,
    )
    position = serializers.IntegerField(
        required=False,
        min_value=0,
    )

    def validate_title(self, value: str) -> str:
        title = value.strip()

        if not title:
            raise serializers.ValidationError(
                "List title is required."
            )

        return title


class BoardListUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=120,
    )

    def validate_title(self, value: str) -> str:
        title = value.strip()

        if not title:
            raise serializers.ValidationError(
                "List title is required."
            )

        return title


class BoardListMoveSerializer(serializers.Serializer):
    position = serializers.IntegerField(
        min_value=0,
    )

class CardReadSerializer(serializers.ModelSerializer):
    board_list_id = serializers.UUIDField(
        read_only=True
    )

    created_by = serializers.UUIDField(
        source="created_by_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Card
        fields = (
            "id",
            "board_list_id",
            "title",
            "description",
            "position",
            "due_at",
            "created_by",
            "created_at",
            "updated_at",
        )


class CardCreateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    due_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )

    position = serializers.IntegerField(
        required=False,
        min_value=0,
    )

    def validate_title(self, value: str) -> str:
        title = value.strip()

        if not title:
            raise serializers.ValidationError(
                "Card title is required."
            )

        return title

    def validate_description(
        self,
        value: str,
    ) -> str:
        return value.strip()


class CardUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=False,
        max_length=200,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    due_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )

    def validate_title(self, value: str) -> str:
        title = value.strip()

        if not title:
            raise serializers.ValidationError(
                "Card title is required."
            )

        return title

    def validate_description(
        self,
        value: str,
    ) -> str:
        return value.strip()

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        return attrs


class CardMoveSerializer(serializers.Serializer):
    destination_list_id = serializers.UUIDField()

    position = serializers.IntegerField(
        min_value=0,
    )

class BoardListWithCardsReadSerializer(
    BoardListReadSerializer
):
    cards = CardReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta(BoardListReadSerializer.Meta):
        fields = (
            BoardListReadSerializer.Meta.fields
            + ("cards",)
        )


class BoardDetailReadSerializer(
    BoardReadSerializer
):
    lists = BoardListWithCardsReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta(BoardReadSerializer.Meta):
        fields = (
            BoardReadSerializer.Meta.fields
            + ("lists",)
        )