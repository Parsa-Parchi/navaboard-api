from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.activity.models import Activity, Notification
from apps.boards.models import Board, BoardList, BoardMembership, Card
from apps.collaboration.models import (
    CardAssignee,
    CardLabel,
    Checklist,
    ChecklistItem,
    Comment,
    Label,
)
from apps.workspaces.models import Workspace, WorkspaceMembership


class Command(BaseCommand):
    help = "Create an idempotent, presentation-ready NavaBoard demo dataset."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        people = [
            ("+989120000001", "admin@navaboard.local", "Parsa Parchi"),
            ("+989120000002", "sara@navaboard.local", "Sara Ahmadi"),
            ("+989120000003", "ali@navaboard.local", "Ali Rezaei"),
            ("+989120000004", "mina@navaboard.local", "Mina Karimi"),
        ]
        users = {}
        for phone, email, name in people:
            user, _ = User.objects.update_or_create(
                phone_number=phone,
                defaults={
                    "email": email,
                    "full_name": name,
                    "is_phone_verified": True,
                    "is_email_verified": True,
                    "is_active": True,
                },
            )
            users[phone] = user

        owner = users[people[0][0]]
        owner.is_staff = True
        owner.is_superuser = True
        owner.set_password(options["admin_password"])
        owner.save()

        workspace, _ = Workspace.objects.update_or_create(
            name="NavaBoard Product Team",
            created_by=owner,
            defaults={"description": "Planning and delivering the NavaBoard launch."},
        )
        roles = [
            (owner, WorkspaceMembership.Role.OWNER),
            (users[people[1][0]], WorkspaceMembership.Role.ADMIN),
            (users[people[2][0]], WorkspaceMembership.Role.MEMBER),
            (users[people[3][0]], WorkspaceMembership.Role.MEMBER),
        ]
        memberships = {}
        for user, role in roles:
            membership, _ = WorkspaceMembership.objects.update_or_create(
                workspace=workspace, user=user, defaults={"role": role}
            )
            memberships[user.phone_number] = membership

        board, _ = Board.objects.update_or_create(
            workspace=workspace,
            name="NavaBoard Launch",
            defaults={
                "description": "Product, engineering, and launch work for the first release.",
                "visibility": Board.Visibility.WORKSPACE,
                "created_by": owner,
            },
        )
        for user, role in roles:
            BoardMembership.objects.update_or_create(
                board=board,
                workspace_membership=memberships[user.phone_number],
                defaults={
                    "role": BoardMembership.Role.ADMIN
                    if role in {WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.ADMIN}
                    else BoardMembership.Role.MEMBER
                },
            )

        lists = {}
        for position, title in enumerate(("Backlog", "In Progress", "Review", "Done")):
            item, _ = BoardList.objects.update_or_create(
                board=board, title=title, defaults={"position": position}
            )
            lists[title] = item

        card_specs = [
            ("Backlog", 0, "Prepare production deployment", "Configure HTTPS, Redis, backups, and provider credentials.", 14),
            ("Backlog", 1, "Design onboarding experience", "Create a simple phone-first onboarding flow for new users.", 10),
            ("In Progress", 0, "Build responsive Kanban board", "Implement drag and drop for lists and cards.", 5),
            ("In Progress", 1, "Integrate OTP authentication", "Connect CSRF initialization, OTP verification, and token refresh.", 3),
            ("Review", 0, "Connect notifications inbox", "Show unread count and polling-based notification history.", 2),
            ("Done", 0, "Finalize OpenAPI documentation", "Validate Swagger schemas and publish frontend examples.", -1),
        ]
        cards = {}
        for list_name, position, title, description, due_days in card_specs:
            card, _ = Card.objects.update_or_create(
                board_list=lists[list_name],
                title=title,
                defaults={
                    "description": description,
                    "position": position,
                    "due_at": timezone.now() + timedelta(days=due_days),
                    "created_by": owner,
                },
            )
            cards[title] = card

        labels = {}
        for name, color in (("Backend", "#2563EB"), ("Frontend", "#7C3AED"), ("High Priority", "#DC2626"), ("Documentation", "#059669")):
            label, _ = Label.objects.update_or_create(
                board=board, name=name, defaults={"color": color}
            )
            labels[name] = label

        label_map = {
            "Prepare production deployment": ("Backend", "High Priority"),
            "Build responsive Kanban board": ("Frontend", "High Priority"),
            "Integrate OTP authentication": ("Backend", "Frontend"),
            "Finalize OpenAPI documentation": ("Documentation",),
        }
        for card_title, names in label_map.items():
            for name in names:
                CardLabel.objects.get_or_create(card=cards[card_title], label=labels[name])

        assignments = {
            "Prepare production deployment": people[2][0],
            "Build responsive Kanban board": people[1][0],
            "Integrate OTP authentication": people[2][0],
            "Connect notifications inbox": people[3][0],
        }
        for card_title, phone in assignments.items():
            CardAssignee.objects.update_or_create(
                card=cards[card_title],
                workspace_membership=memberships[phone],
                defaults={"assigned_by": owner},
            )

        auth_card = cards["Integrate OTP authentication"]
        checklist, _ = Checklist.objects.update_or_create(
            card=auth_card, title="Frontend integration", defaults={"position": 0}
        )
        for position, (title, completed) in enumerate(
            (("Initialize CSRF token", True), ("Request OTP code", True), ("Verify OTP and keep access token in memory", True), ("Refresh access token with credentials included", False))
        ):
            ChecklistItem.objects.update_or_create(
                checklist=checklist,
                title=title,
                defaults={"position": position, "is_completed": completed},
            )

        Comment.objects.update_or_create(
            card=cards["Build responsive Kanban board"],
            author=users[people[1][0]],
            body="The desktop layout is ready. I am refining the mobile drag-and-drop behavior.",
        )
        Comment.objects.update_or_create(
            card=cards["Connect notifications inbox"],
            author=users[people[3][0]],
            body="Polling every 30 seconds works well for the initial release.",
        )

        activity_specs = [
            ("board.created", board, None, owner),
            ("card.updated", board, auth_card, users[people[2][0]]),
            ("comment.created", board, cards["Connect notifications inbox"], users[people[3][0]]),
        ]
        for action, activity_board, card, actor in activity_specs:
            activity, _ = Activity.objects.get_or_create(
                workspace=workspace,
                board=activity_board,
                card=card,
                actor=actor,
                action=action,
                resource_id=str((card or activity_board).pk),
            )
            for recipient in users.values():
                if recipient != actor:
                    Notification.objects.get_or_create(recipient=recipient, activity=activity)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write("Admin URL: http://127.0.0.1:8000/admin/")
        self.stdout.write(f"Admin phone: {owner.phone_number}")
