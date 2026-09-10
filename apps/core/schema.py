"""Frontend-facing descriptions shared by live Swagger and exported OpenAPI."""
from django.conf import settings
from drf_spectacular.openapi import AutoSchema


# class: (resource, permission contract, operation-specific guidance)
RESOURCES = {
    "WorkspaceListCreateAPIView": ("workspaces", "Authentication required. GET returns only your memberships; POST makes you the owner.", "Create with name and optional description."),
    "WorkspaceDetailAPIView": ("workspace", "Members may read; owner/admin may update; only owner may delete.", "PATCH changes supplied fields only. Deleted workspaces and their boards are inaccessible."),
    "WorkspaceMembershipListCreateAPIView": ("workspace members", "Members may list. Owner/admin may add existing active users; admins may only add regular members.", "Supply phone_number and role (member/admin). Use membership id from the response when changing/removing members."),
    "WorkspaceMembershipDetailAPIView": ("workspace membership", "Only owner changes roles. Members may leave; owner/admin removal is restricted by role. Owner must transfer ownership before leaving.", "membership_id is the membership UUID, not the user UUID."),
    "WorkspaceOwnershipTransferAPIView": ("workspace ownership", "Only current owner; destination must already be a workspace member.", "Supply new_owner_phone_number. Previous owner becomes admin. Returns the new owner's membership."),
    "BoardListCreateAPIView": ("boards in workspace", "Workspace membership required. Only visible boards are listed. Creator becomes board admin.", "visibility is private or workspace. Workspace-visible boards are readable by workspace members; editing still requires board membership."),
    "BoardDetailAPIView": ("board", "Workspace owner or board member may read; workspace-visible boards also allow workspace members to read. Board admin/workspace owner may update or delete.", "GET includes ordered lists and cards for initial board hydration. DELETE soft-deletes the board."),
    "BoardMembershipListCreateAPIView": ("board members", "Board readers may list. Board admin/workspace owner may add.", "Supply phone_number of an existing workspace member and role (admin/member)."),
    "BoardMembershipDetailAPIView": ("board membership", "Board administrator/workspace owner access is required. Workspace owner retains management access even without board membership.", "membership_id is a board membership UUID. Removing membership revokes private-board access."),
    "BoardListListCreateAPIView": ("board lists", "Board readers may list; board members/workspace owner may create.", "Lists are ordered by zero-based position. Omit position to append."),
    "BoardListDetailAPIView": ("board list", "Board member/workspace owner required.", "Update title. DELETE soft-deletes the list and makes its cards inaccessible; remaining positions are compacted."),
    "BoardListMoveAPIView": ("board list position", "Board member/workspace owner required.", "Send position from 0 to list count minus 1. Re-fetch ordered lists after drag-and-drop."),
    "CardListCreateAPIView": ("cards in list", "Board readers may list; board members/workspace owner may create.", "Send title, optional description/due_at/position. due_at is an ISO 8601 timestamp with timezone. Omit position to append."),
    "CardDetailAPIView": ("card", "Board readers may read; board members/workspace owner may update/delete.", "PATCH only supplied fields. Send due_at: null to clear a deadline. DELETE soft-deletes and compacts sibling positions."),
    "CardMoveAPIView": ("card position", "Board member/workspace owner required.", "Send destination_list_id and zero-based position. Destination must be on the same board. Moving within a list accepts 0..count-1; between lists accepts 0..destination count. Re-fetch both lists."),
    "BoardLabelListCreateAPIView": ("board labels", "Board readers may list; board admin/workspace owner may create.", "Send name and color. Use returned label UUID to attach to cards."),
    "BoardLabelDetailAPIView": ("board label", "Board admin/workspace owner required.", "Update name/color or delete the board label."),
    "CardLabelCreateAPIView": ("card label", "Board member/workspace owner required.", "Send label_id belonging to the same board."),
    "CardLabelDetailAPIView": ("card label link", "Board member/workspace owner required.", "Removes only the association; the board label remains available."),
    "ChecklistListCreateAPIView": ("card checklists", "Board readers may list; board members/workspace owner may create.", "Send title to append a checklist. Read response includes its ordered items."),
    "ChecklistDetailAPIView": ("checklist", "Board member/workspace owner required.", "Update title or soft-delete the checklist; items become inaccessible."),
    "ChecklistMoveAPIView": ("checklist position", "Board member/workspace owner required.", "Send zero-based position within the card (0..count-1)."),
    "ChecklistItemCreateAPIView": ("checklist item", "Board member/workspace owner required.", "Send title; the item is appended with is_completed=false."),
    "ChecklistItemDetailAPIView": ("checklist item", "Board member/workspace owner required.", "PATCH title and/or is_completed. DELETE compacts remaining item positions."),
    "ChecklistItemMoveAPIView": ("checklist item position", "Board member/workspace owner required.", "Send zero-based position within the checklist (0..count-1)."),
    "CommentListCreateAPIView": ("card comments", "Board readers may list; board members/workspace owner may comment.", "Send nonblank body. Author is assigned from the access token. Card participants receive an in-app notification."),
    "CommentDetailAPIView": ("comment", "Only author or board admin/workspace owner may modify, with current board access.", "PATCH body or DELETE. Deleted comments are hidden."),
    "CardAssigneeListCreateAPIView": ("card assignees", "Board readers may list; board admin/workspace owner may assign.", "Send phone_number of an existing workspace member. Assignment does not grant private-board access: add board membership separately if needed."),
    "CardAssigneeDetailAPIView": ("card assignee", "Board admin/workspace owner required.", "assignee_id is the assignment UUID, not a user UUID. Removes the card assignment."),
}

AUTH = {
    "OTPRequestAPIView": ("Request phone login code", "First step for both registration and login. Send an Iranian mobile number (09121234567 or +989121234567). Code expires in two minutes. In development only, development_otp_code may be returned; otherwise delivery uses the configured SMS provider.", {"phone_number": "09121234567"}),
    "OTPVerificationAPIView": ("Verify phone code and sign in", "Send phone_number and six-digit code. First successful verification creates the user. JSON contains access, token_type and user; refresh is set only in an HttpOnly cookie. Include credentials and X-CSRFToken obtained from GET /api/auth/csrf/.", {"phone_number": "09121234567", "code": "123456"}),
    "TokenRefreshAPIView": ("Rotate refresh cookie", "POST with no body, credentials included and X-CSRFToken. Returns a new access token and rotates the HttpOnly refresh cookie; old refresh cannot be reused. An expired Authorization header is ignored. Serialize concurrent refresh requests in the frontend. Invalid/missing refresh returns 400; sign in again.", None),
    "LogoutAPIView": ("Sign out this browser", "POST with credentials and X-CSRFToken. Revokes this browser's refresh token and clears its cookie. Works with expired access tokens; repeated logout succeeds. Discard the frontend access token; issued access tokens expire normally.", None),
    "CurrentUserProfileAPIView": ("current user profile", "Bearer token required. GET reads profile; PATCH/PUT changes full_name. Phone/email/verification flags are read-only: use their verification endpoints.", {"full_name": "Parsa"}),
    "EmailPasswordLoginAPIView": ("Sign in with optional verified email", "For existing users who attached and verified email and set a password. Send email/password with credentials and X-CSRFToken. Returns access JSON and HttpOnly refresh cookie.", {"email": "parsa@example.com", "password": "your-password"}),
    "EmailVerificationRequestAPIView": ("Request optional email verification", "Bearer token required. After phone login, send the email to attach. Code expires in ten minutes; the email is not changed until confirmation.", {"email": "parsa@example.com"}),
    "EmailVerificationConfirmAPIView": ("Attach verified email", "Bearer token required. Send the same email and its six-digit code. A code is bound to the requesting user and cannot be reused.", {"email": "parsa@example.com", "code": "123456"}),
    "SetInitialPasswordAPIView": ("Set optional login password", "Bearer token required. Sets the first password; existing passwords must use change. All sessions are revoked; sign in again with phone OTP.", {"password": "use-a-strong-password"}),
    "ChangePasswordAPIView": ("Change login password", "Bearer token required. Supply current_password and new_password. Revokes sessions and clears the refresh cookie; sign in again.", {"current_password": "old-password", "new_password": "new-strong-password"}),
    "PasswordResetRequestAPIView": ("Request password reset", "Send account phone_number. A password-reset SMS code is generated for the active account.", {"phone_number": "09121234567"}),
    "PasswordResetConfirmAPIView": ("Reset password with phone code", "Send phone_number, code and new_password. Successful reset revokes existing sessions. Sign in again afterward.", {"phone_number": "09121234567", "code": "123456", "new_password": "new-strong-password"}),
    "PhoneChangeRequestAPIView": ("Request new phone verification", "Bearer token required. Send the destination phone_number. Code is bound to the current user and new number.", {"phone_number": "09121234568"}),
    "PhoneChangeConfirmAPIView": ("Confirm phone number change", "Bearer token required. Send the destination phone_number and code. The number must not belong to another user.", {"phone_number": "09121234568", "code": "123456"}),
}

EXAMPLES = {
    "WorkspaceListCreateAPIView": {"name": "Product", "description": "Product planning"},
    "WorkspaceDetailAPIView": {"name": "Product team"},
    "WorkspaceMembershipListCreateAPIView": {"phone_number": "09121234567", "role": "member"},
    "WorkspaceMembershipDetailAPIView": {"role": "admin"},
    "WorkspaceOwnershipTransferAPIView": {"new_owner_phone_number": "09121234567"},
    "BoardListCreateAPIView": {"name": "Sprint", "visibility": "private"},
    "BoardDetailAPIView": {"name": "Current sprint"},
    "BoardMembershipListCreateAPIView": {"phone_number": "09121234567", "role": "member"},
    "BoardMembershipDetailAPIView": {"role": "admin"},
    "BoardListListCreateAPIView": {"title": "Todo", "position": 0},
    "BoardListDetailAPIView": {"title": "In progress"},
    "BoardListMoveAPIView": {"position": 0},
    "CardListCreateAPIView": {"title": "Implement login", "description": "Phone OTP flow", "position": 0},
    "CardDetailAPIView": {"title": "Review login", "due_at": None},
    "CardMoveAPIView": {"destination_list_id": "6b6c884d-2b63-4f53-8dd2-8da6dc58e3f6", "position": 0},
    "BoardLabelListCreateAPIView": {"name": "Urgent", "color": "#ff0000"},
    "BoardLabelDetailAPIView": {"name": "High priority"},
    "CardLabelCreateAPIView": {"label_id": "6b6c884d-2b63-4f53-8dd2-8da6dc58e3f6"},
    "ChecklistListCreateAPIView": {"title": "Acceptance criteria"},
    "ChecklistDetailAPIView": {"title": "Release checklist"},
    "ChecklistMoveAPIView": {"position": 0},
    "ChecklistItemCreateAPIView": {"title": "Review permissions"},
    "ChecklistItemDetailAPIView": {"is_completed": True},
    "ChecklistItemMoveAPIView": {"position": 0},
    "CommentListCreateAPIView": {"body": "Ready for review"},
    "CommentDetailAPIView": {"body": "Review complete"},
    "CardAssigneeListCreateAPIView": {"phone_number": "09121234567"},
}


class FrontendAutoSchema(AutoSchema):
    def get_operation(self, *args, **kwargs):
        name = self.view.__class__.__name__
        if name.startswith("EmailSignup") and not settings.AUTH_ENABLE_EMAIL_SIGNUP:
            return None
        operation = super().get_operation(*args, **kwargs)
        if operation is None:
            return None
        method = self.method.lower()
        verb = {"get": "Get", "post": "Create", "patch": "Update", "put": "Update", "delete": "Delete"}.get(method, method)
        if name in RESOURCES:
            resource, permissions, guidance = RESOURCES[name]
            operation["summary"] = f"{verb} {resource}"
            operation["description"] = f"{permissions}\n\n{guidance}\n\nIdentifiers are UUIDs. Send Authorization: Bearer <access>. Successful mutations are recorded in activity history. Validation errors return 400; insufficient permissions return 403; missing or invisible objects return 404. Collection responses are arrays unless a pagination envelope is shown in the response schema."
            if name in EXAMPLES and method in {"post", "patch", "put"}:
                for content in operation.get("requestBody", {}).get("content", {}).values():
                    content["example"] = EXAMPLES[name]
        if name in AUTH:
            summary, description, example = AUTH[name]
            operation["summary"] = f"{verb} {summary}" if name == "CurrentUserProfileAPIView" else summary
            operation["description"] = description + "\n\nValidation errors return 400; throttling returns 429 with Retry-After. Code delivery failure returns 503. Never send refresh tokens in JSON."
            if example and method in {"post", "put", "patch"}:
                for content in operation.get("requestBody", {}).get("content", {}).values():
                    content["example"] = example
        if name in {"OTPVerificationAPIView", "EmailPasswordLoginAPIView", "TokenRefreshAPIView", "LogoutAPIView"}:
            operation.setdefault("parameters", []).append({
                "name": "X-CSRFToken", "in": "header", "required": True,
                "schema": {"type": "string"},
                "description": "csrfToken returned by GET /api/auth/csrf/; include the browser cookies too.",
            })
        if name in RESOURCES or name in AUTH:
            errors = {"400": "Invalid input; field errors or a list of validation messages.", "403": "Insufficient permission or invalid CSRF."}
            if name in RESOURCES:
                errors.update({"401": "Missing or invalid access token.", "404": "Not found or not visible to this user."})
            for code, description in errors.items():
                schema = {"type": "object", "properties": {"detail": {"type": "string"}}}
                if code == "400":
                    schema = {"oneOf": [{"type": "array", "items": {"type": "string"}}, {"type": "object", "additionalProperties": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}}]}
                operation["responses"].setdefault(code, {"description": description, "content": {"application/json": {"schema": schema}}})
        return operation
