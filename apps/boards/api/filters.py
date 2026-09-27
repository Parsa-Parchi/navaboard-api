"""Card search shared by the global results page and board hydration."""
import shlex
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.collaboration.models import Attachment, CardAssignee, CardLabel, Checklist, ChecklistItem, Comment


class QueryBooleanField(serializers.BooleanField):
    # QueryDict is treated as an HTML form by DRF. An omitted filter must stay
    # absent, not become False (the checkbox default used by BooleanField).
    default_empty_html = serializers.empty


class CardSearchParameters(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=200, allow_blank=True,
        help_text='Words/double-quoted phrases, @me, #Label, name:, description:, board:, list:, label:, comment:, checklist:, has:members/labels/attachments, due:overdue/day/week/none. Prefix a token with - to exclude. All terms must match. Unsupported operators return 400.')
    workspace_id = serializers.UUIDField(required=False)
    board_id = serializers.UUIDField(required=False)
    list_id = serializers.UUIDField(required=False)
    assigned_to_me = QueryBooleanField(required=False)
    member_ids = serializers.ListField(child=serializers.UUIDField(), required=False,
        allow_empty=False, max_length=20, help_text="Repeat member_ids for user UUIDs. Matches any selected member.")
    label_ids = serializers.ListField(child=serializers.UUIDField(), required=False,
        allow_empty=False, max_length=20, help_text="Repeat label_ids for label UUIDs. Matches any selected label.")
    has_members = QueryBooleanField(required=False)
    has_labels = QueryBooleanField(required=False)
    has_attachments = QueryBooleanField(required=False)
    due_before = serializers.DateTimeField(required=False)
    due_after = serializers.DateTimeField(required=False)
    due = serializers.ChoiceField(required=False, choices=["overdue", "day", "week", "none"],
        help_text="overdue: before now; day/week: next 24h/7d; none: no deadline.")

    def validate(self, values):
        if values.get("due_before") and values.get("due_after") and values["due_after"] > values["due_before"]:
            raise serializers.ValidationError({"due_after": "Must not be later than due_before."})
        if "q" in values:
            values["terms"] = parse_query(values["q"])
        return values


def parse_query(text):
    try:
        lexer = shlex.shlex(text, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.quotes = '"'
        lexer.escape = ""
        terms = list(lexer)
    except ValueError as exc:
        raise serializers.ValidationError({"q": "Close all quoted phrases."}) from exc
    if len(terms) > 20:
        raise serializers.ValidationError({"q": "Use at most 20 search terms."})
    parsed = []
    for token in terms:
        negative = token.startswith("-")
        token = token[1:] if negative else token
        if token == "@me":
            key, value = "member", "me"
        elif token.startswith("#"):
            key, value = "label", token[1:]
        elif ":" in token:
            key, value = token.split(":", 1)
            key = key.lower()
            if key not in {"name", "description", "board", "list", "label", "comment", "checklist", "has", "due", "member"}:
                raise serializers.ValidationError({"q": f"Unsupported search operator: {key}."})
        else:
            key, value = "text", token
        if not value:
            raise serializers.ValidationError({"q": "Search terms must not be empty."})
        if key == "has" and value not in {"members", "labels", "attachments"}:
            raise serializers.ValidationError({"q": "has supports members, labels or attachments."})
        if key == "due" and value not in {"overdue", "day", "week", "none"}:
            raise serializers.ValidationError({"q": "due supports overdue, day, week or none."})
        if key == "member" and value != "me":
            raise serializers.ValidationError({"q": "Use @me, member:me or the member_ids parameter."})
        parsed.append((negative, key, value))
    return parsed


def related_cards(model, **lookups):
    # Subqueries preserve correct negation and exclude soft-deleted related rows.
    return Q(pk__in=model.objects.filter(**lookups).values("card_id"))


def due_condition(value, now):
    if value == "none":
        return Q(due_at__isnull=True)
    if value == "overdue":
        return Q(due_at__lt=now)
    return Q(due_at__gte=now, due_at__lte=now + timedelta(days=1 if value == "day" else 7))


def has_condition(value):
    if value == "members":
        return related_cards(CardAssignee)
    if value == "labels":
        return related_cards(CardLabel, label__deleted_at__isnull=True)
    return related_cards(Attachment)


def term_condition(key, value, user, now):
    paths = {"name": "title", "description": "description", "board": "board_list__board__name", "list": "board_list__title"}
    if key in paths:
        return Q(**{paths[key] + "__icontains": value})
    if key == "member":
        return related_cards(CardAssignee, workspace_membership__user=user)
    if key == "label":
        return related_cards(CardLabel, label__deleted_at__isnull=True, label__name__icontains=value)
    if key == "comment":
        return related_cards(Comment, body__icontains=value)
    if key == "checklist":
        items = ChecklistItem.objects.filter(title__icontains=value, checklist__deleted_at__isnull=True).values("checklist__card_id")
        return related_cards(Checklist, title__icontains=value) | Q(pk__in=items)
    if key == "has":
        return has_condition(value)
    if key == "due":
        return due_condition(value, now)
    return Q(title__icontains=value) | Q(description__icontains=value)


def filter_cards(queryset, values, user):
    now = timezone.now()
    for name, lookup in {"workspace_id": "board_list__board__workspace_id", "board_id": "board_list__board_id", "list_id": "board_list_id", "due_before": "due_at__lte", "due_after": "due_at__gte"}.items():
        if name in values:
            queryset = queryset.filter(**{lookup: values[name]})
    if "assigned_to_me" in values:
        condition = related_cards(CardAssignee, workspace_membership__user=user)
        queryset = queryset.filter(condition if values["assigned_to_me"] else ~condition)
    if "member_ids" in values:
        queryset = queryset.filter(related_cards(CardAssignee, workspace_membership__user_id__in=values["member_ids"]))
    if "label_ids" in values:
        queryset = queryset.filter(related_cards(CardLabel, label_id__in=values["label_ids"], label__deleted_at__isnull=True))
    for field, kind in {"has_members": "members", "has_labels": "labels", "has_attachments": "attachments"}.items():
        if field in values:
            condition = has_condition(kind)
            queryset = queryset.filter(condition if values[field] else ~condition)
    if "due" in values:
        queryset = queryset.filter(due_condition(values["due"], now))
    for negative, key, value in values.get("terms", []):
        condition = term_condition(key, value, user, now)
        queryset = queryset.filter(~condition if negative else condition)
    return queryset
