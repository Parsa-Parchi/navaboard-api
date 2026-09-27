"""Validated, literal text search for resource pickers."""
from django.db.models import Q
from rest_framework import serializers


class TextSearchParameters(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=200,
                              help_text="Case-insensitive substring of name or description.")


def filter_named_resources(queryset, params):
    serializer = TextSearchParameters(data=params)
    serializer.is_valid(raise_exception=True)
    term = serializer.validated_data.get("q", "")
    if term:
        queryset = queryset.filter(Q(name__icontains=term) | Q(description__icontains=term))
    return queryset
