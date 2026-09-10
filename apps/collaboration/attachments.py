import uuid

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema, OpenApiTypes
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.mixins import ActivityMutationMixin
from apps.boards.api.permissions import CanEditBoard
from apps.collaboration.api.views import _get_visible_card
from apps.collaboration.models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ("id", "card", "original_name", "size", "uploaded_by", "created_at")
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Private attachment. Maximum size is ATTACHMENT_MAX_BYTES (default 10 MiB). Download through the authenticated endpoint.")

    def validate_file(self, value):
        if value.size > settings.ATTACHMENT_MAX_BYTES:
            raise serializers.ValidationError("Attachment exceeds the configured size limit.")
        return value


class AttachmentList(ActivityMutationMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["Attachments"], summary="List private card attachments", description="Board readers may list metadata. Download each file through its authenticated content endpoint.", responses=AttachmentSerializer(many=True))
    def get(self, request, card_id):
        card = _get_visible_card(user=request.user, card_id=card_id)
        return Response(AttachmentSerializer(card.attachments.all(), many=True).data)

    @extend_schema(tags=["Attachments"], summary="Upload a card attachment", description="Board edit permission required. Send multipart/form-data with file. Files are private and served as downloads, never as inline executable content.", request=UploadSerializer, responses={201: AttachmentSerializer})
    def post(self, request, card_id):
        card = _get_visible_card(user=request.user, card_id=card_id)
        if not CanEditBoard().has_object_permission(request, self, card):
            raise PermissionDenied(CanEditBoard.message)
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data["file"]
        item = Attachment(card=card, uploaded_by=request.user, original_name=uploaded.name[:255], size=uploaded.size)
        # Random storage names do not retain user-controlled extensions or paths.
        item.file.save(uuid.uuid4().hex, uploaded, save=False)
        try:
            item.save()
        except Exception:
            item.file.delete(save=False)
            raise
        return Response(AttachmentSerializer(item).data, status=201)


class AttachmentDetail(ActivityMutationMixin, APIView):
    @extend_schema(tags=["Attachments"], summary="Delete a card attachment", description="Board edit permission required. Soft-deletes the metadata and denies future downloads. Physical storage is retained for administrative retention/backup policies.", responses={204: None})
    def delete(self, request, card_id, attachment_id):
        card = _get_visible_card(user=request.user, card_id=card_id)
        if not CanEditBoard().has_object_permission(request, self, card):
            raise PermissionDenied(CanEditBoard.message)
        item = get_object_or_404(Attachment.objects, pk=attachment_id, card=card)
        item.delete()
        return Response(status=204)


class AttachmentContent(APIView):
    @extend_schema(tags=["Attachments"], summary="Download a private attachment", description="Requires Bearer authentication and current board access. Fetch as a blob in the frontend. Response is application/octet-stream with Content-Disposition: attachment; no public media URL is exposed.", responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, card_id, attachment_id):
        card = _get_visible_card(user=request.user, card_id=card_id)
        item = get_object_or_404(Attachment.objects, pk=attachment_id, card=card)
        try:
            stream = item.file.open("rb")
        except FileNotFoundError as exc:
            raise NotFound("Attachment content is unavailable.") from exc
        response = FileResponse(stream, as_attachment=True, filename=item.original_name, content_type="application/octet-stream")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


urlpatterns = [
    path("cards/<uuid:card_id>/attachments/", AttachmentList.as_view(), name="attachment-list"),
    path("cards/<uuid:card_id>/attachments/<uuid:attachment_id>/", AttachmentDetail.as_view(), name="attachment-detail"),
    path("cards/<uuid:card_id>/attachments/<uuid:attachment_id>/content/", AttachmentContent.as_view(), name="attachment-content"),
]
