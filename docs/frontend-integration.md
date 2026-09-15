# NavaBoard frontend integration guide

This guide describes the implemented API contract. Use the live OpenAPI schema
for exact required fields, types, response objects and endpoint-specific permissions.

## 1. Connection and API conventions

| Resource | Location |
| --- | --- |
| API base path | `/api/` |
| Interactive Swagger | `/api/docs/` |
| Live OpenAPI | `/api/schema/` |
| Exported OpenAPI | `schema.yml` in this repository |
| Database readiness | `GET /health/` |

Use trailing slashes. Send JSON except for attachment uploads. IDs are UUIDs;
user IDs, workspace membership IDs, board membership IDs and assignee IDs are
different identifiers. Do not substitute one for another.

The default browser integration is **same-origin**: serve the frontend and proxy
`/api/` to Django. For development, proxy `/api/` from your frontend dev server to
`http://127.0.0.1:8000`. Use one consistent browser hostname. Preserve cookies and
ensure the origin/host forwarded to Django satisfies its CSRF checks. If the proxy
preserves the dev-server Origin, add that exact origin to `CSRF_TRUSTED_ORIGINS`.

Direct requests between different origins require an explicit CORS allowlist at
the reverse proxy, credentials support, allowed Authorization/Content-Type/X-CSRFToken
headers, and `CSRF_TRUSTED_ORIGINS`. There is no CORS middleware in this repository.
Do not combine credentialed requests with `Access-Control-Allow-Origin: *`.
Cross-site cookies additionally require SameSite=None and Secure and may be blocked
by browser third-party-cookie policies. Prefer the same-origin arrangement.

## 2. Phone-first authentication

Phone OTP is the default registration and login flow. Email is optional and added
after signing in. Do not use `/api/auth/email/signup/request/` or `/confirm/`:
these legacy routes return 410 by default and are excluded from Swagger.

### Initialize CSRF

```http
GET /api/auth/csrf/
```

Include browser credentials. The response contains `csrfToken`; the browser also
stores a CSRF cookie. Keep the returned token in memory and send it in `X-CSRFToken`
on OTP verification, email login, refresh and logout POST requests.

### Request a code

```http
POST /api/auth/otp/request/
Content-Type: application/json

{"phone_number":"09121234567"}
```

Iranian mobile numbers are normalized; `09121234567` and `+989121234567` identify
the same number. A 201 response includes `detail` and `expires_at`. The code expires
after two minutes. `development_otp_code` may be present only in development.
Do not require or display that field in production. Respect 429 and `Retry-After`.

### Verify and sign in

```http
POST /api/auth/otp/verify/
Content-Type: application/json
X-CSRFToken: <csrfToken>

{"phone_number":"09121234567","code":"123456"}
```

Send `credentials: "include"`. Successful verification creates an account if needed.
The JSON response contains `access`, `token_type`, `user_created` and `user`.
The backend sets refresh in an **HttpOnly cookie through Set-Cookie**, never JSON.
JavaScript must not read, manufacture or store the refresh token. Keep access in memory.

Send `Authorization: Bearer <access>` on protected endpoints. Access lasts 15 minutes;
refresh lasts 14 days under the current settings.

### Refresh, reload and logout

- On page reload, initialize CSRF, attempt `POST /api/auth/token/refresh/`, then fetch `/api/auth/me/`.
- Refresh has no JSON body. Include cookies and `X-CSRFToken`. It returns `access` and `token_type` and rotates the refresh cookie.
- Old refresh tokens cannot be reused. Coalesce concurrent refresh requests within the application; coordinate between tabs if the frontend supports multiple active tabs.
- On a protected API's 401, refresh once and retry that request once. Never refresh recursively or treat 403 as token expiry.
- An invalid/missing refresh returns 400; a revoked/inactive account may return an authentication error. Require sign-in again. Treat 429 and transient transport/server failures separately from a definitive session rejection.
- Logout is `POST /api/auth/logout/` with cookies and CSRF, no body. It works without a valid access token, revokes this browser's refresh and clears its cookie. Clear frontend access after successful logout.
- Existing access tokens expire normally after logout. Setting/changing/resetting the password invalidates sessions; require sign-in again.

### Browser request example

This illustrates JSON requests and single-flight refresh. The caller supplies UI
handling for validation errors, rate limits, network failures and sign-in prompts.
Use separate helpers for file upload/download as shown below.

```javascript
let access = null;
let csrfToken = null;
let refreshInFlight = null;

async function readJson(response) {
  if (response.status === 204) return null;
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; }
  catch { data = { detail: text || 'Unexpected response' }; }
  if (!response.ok) {
    const error = new Error(data?.detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = data;
    error.retryAfter = response.headers.get('Retry-After');
    throw error;
  }
  return data;
}

async function initializeCsrf() {
  const response = await fetch('/api/auth/csrf/', { credentials: 'include' });
  csrfToken = (await readJson(response)).csrfToken;
}

async function publicPost(path, body, needsCsrf = false) {
  if (needsCsrf && !csrfToken) await initializeCsrf();
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (needsCsrf) headers['X-CSRFToken'] = csrfToken;
  return readJson(await fetch(`/api/${path}`, {
    method: 'POST', credentials: 'include', headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  }));
}

async function verifyPhone(phone_number, code) {
  const data = await publicPost('auth/otp/verify/', { phone_number, code }, true);
  access = data.access;
  return data.user;
}

async function refreshAccess() {
  if (!refreshInFlight) {
    refreshInFlight = publicPost('auth/token/refresh/', undefined, true)
      .then(data => { access = data.access; })
      .catch(error => {
        if ([400, 401].includes(error.status)) access = null;
        throw error;
      })
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

async function api(path, { method = 'GET', body } = {}) {
  const send = () => fetch(`/api/${path}`, {
    method, credentials: 'include',
    headers: {
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  let response = await send();
  if (response.status === 401) {
    await refreshAccess();
    response = await send();
  }
  return readJson(response);
}

// Login screen:
// await publicPost('auth/otp/request/', { phone_number: '09121234567' });
// const user = await verifyPhone('09121234567', codeEnteredByUser);
// const workspaces = await api('workspaces/');

async function logout() {
  await publicPost('auth/logout/', undefined, true);
  access = null;
}
```

Do not automatically retry writes after a timeout: the server may have committed
them even if the response was lost. Re-fetch state before deciding whether to repeat.

## 3. Profile and optional email

All paths below start with `/api/auth/`. Protected routes require Bearer authentication.

| Method / path | Input and behavior |
| --- | --- |
| GET `me/` | Read the current profile |
| PATCH / PUT `me/` | `full_name`; phone, email and verification flags are read-only |
| POST `email/verification/request/` | `email`; request a code for the signed-in user |
| POST `email/verification/confirm/` | Same `email` and six-digit `code`; attach the verified address |
| POST `password/set/` | `password`; set the first optional password, then sign in again |
| POST `password/change/` | `current_password`, `new_password`; then sign in again |
| POST `email/login/` | `email`, `password`; public login with CSRF/cookies, for eligible existing users |
| POST `phone/change/request/` | Destination `phone_number` |
| POST `phone/change/confirm/` | Destination `phone_number`, `code` |
| POST `password/reset/request/` | Public request using `phone_number` |
| POST `password/reset/confirm/` | Public confirmation using `phone_number`, `code`, `new_password` |

Email verification codes last ten minutes and are bound to the requesting user.
Do not PATCH email or phone directly. OTP purpose is selected by the endpoint;
never supply a `purpose` field.

## 4. Workspace-to-card flow

```javascript
const workspace = await api('workspaces/', {
  method: 'POST', body: { name: 'Product team' }
});
const board = await api(`workspaces/${workspace.id}/boards/`, {
  method: 'POST', body: { name: 'Sprint', visibility: 'private' }
});
const list = await api(`boards/${board.id}/lists/`, {
  method: 'POST', body: { title: 'Todo' }
});
const card = await api(`boards/${board.id}/lists/${list.id}/cards/`, {
  method: 'POST', body: { title: 'Implement login', description: 'Phone OTP flow' }
});
```

The workspace creator becomes owner; the board creator becomes board admin.
`GET /api/boards/{board_id}/` includes ordered lists and cards for initial rendering.
Fetch comments, labels, checklists, assignees and attachments from their own routes.
Card `due_at` accepts an ISO 8601 timestamp with timezone; send null to clear it.

### Workspace and membership routes

| Route | Methods and purpose |
| --- | --- |
| `/api/workspaces/` | GET your workspaces; POST `name`, optional `description` |
| `/api/workspaces/{workspace_id}/` | GET; PATCH fields; DELETE as owner |
| `/api/workspaces/{workspace_id}/members/` | GET; POST `phone_number`, `role` |
| `/api/workspaces/{workspace_id}/members/{membership_id}/` | PATCH `role`; DELETE membership |
| `/api/workspaces/{workspace_id}/transfer-ownership/` | POST `new_owner_phone_number` |

Members must already have accounts. Roles assigned through member creation are
`admin` or `member`; use ownership transfer for `owner`. The destination owner
must already belong to the workspace. The previous owner becomes admin.

### Boards, lists and cards

| Route | Methods and purpose |
| --- | --- |
| `/api/workspaces/{workspace_id}/boards/` | GET visible boards; POST `name`, optional `description`, `visibility` |
| `/api/boards/{board_id}/` | GET hydrated board; PATCH fields; DELETE |
| `/api/boards/{board_id}/members/` | GET; POST workspace member `phone_number`, `role` (`admin`/`member`) |
| `/api/boards/{board_id}/members/{membership_id}/` | PATCH `role`; DELETE |
| `/api/boards/{board_id}/lists/` | GET; POST `title`, optional `position` |
| `/api/boards/{board_id}/lists/{list_id}/` | PATCH `title`; DELETE |
| `/api/boards/{board_id}/lists/{list_id}/move/` | POST `position` |
| `/api/boards/{board_id}/lists/{list_id}/cards/` | GET; POST `title`, optional `description`, `due_at`, `position` |
| `/api/boards/{board_id}/cards/{card_id}/` | GET; PATCH fields; DELETE |
| `/api/boards/{board_id}/cards/{card_id}/move/` | POST `destination_list_id`, `position` |

### Permissions

| Role | Capabilities |
| --- | --- |
| Workspace owner | Manage workspace and all its boards |
| Workspace admin | Edit workspace; manage regular workspace members; no automatic private-board access |
| Workspace member | Read workspace and workspace-visible boards |
| Board admin | Manage board, board membership, board labels and card assignees |
| Board member | Edit board content, cards and checklists; comment; attach/detach card labels |

Workspace visibility grants reading, not automatic editing. Workspace owners retain
board management access even without board membership. Only the comment author or
an authorized board administrator may edit/delete a comment, with current board access.
Only the workspace owner can change workspace roles. Members can leave subject to
owner protection; transfer ownership before the owner leaves. Server checks remain
authoritative even if the UI hides unavailable actions.

### Drag and drop

Positions are zero-based. Omit position on supported creation routes to append.
Move endpoints operate within their parent; cards can move only within the same board.

```javascript
await api(`boards/${board.id}/cards/${card.id}/move/`, {
  method: 'POST', body: { destination_list_id: destinationListId, position: 0 }
});
```

Within one list, use 0..count-1. Moving a card to another list permits
0..destination count. List/checklist/item moves use 0..count-1. Re-fetch affected
lists or the board after a successful move and after a concurrent-change error.
Do not PATCH position or a card's parent directly.

## 5. Collaboration

All routes below start with `/api/`.

| Route | Methods and input |
| --- | --- |
| `boards/{board_id}/labels/` | GET; POST `name`, `color` |
| `boards/{board_id}/labels/{label_id}/` | PATCH `name`/`color`; DELETE |
| `cards/{card_id}/labels/` | GET attached labels; POST `label_id` belonging to the same board |
| `cards/{card_id}/labels/{label_id}/` | DELETE the association, retaining the board label |
| `cards/{card_id}/checklists/` | GET ordered checklists/items; POST `title` |
| `checklists/{checklist_id}/` | PATCH `title`; DELETE |
| `checklists/{checklist_id}/move/` | POST `position` |
| `checklists/{checklist_id}/items/` | POST `title`; new item starts incomplete |
| `checklist-items/{item_id}/` | PATCH `title` and/or `is_completed`; DELETE |
| `checklist-items/{item_id}/move/` | POST `position` |
| `cards/{card_id}/comments/` | GET; POST nonblank `body` |
| `comments/{comment_id}/` | PATCH `body`; DELETE |
| `cards/{card_id}/members/` | GET assignees; POST `phone_number` of a workspace member |
| `cards/{card_id}/members/{assignee_id}/` | DELETE assignment |

Author/creator is inferred from authentication. Assignment does not grant access
to a private board; add board membership separately when needed.

## 6. Search, activity and notifications

`GET /api/cards/` searches accessible cards. Supported filters combine:
`q` (title/description), `workspace_id`, `board_id`, `assigned_to_me`, `due_before`,
`due_after`. Dates use ISO 8601 with timezone. Deleted/inaccessible ancestors are excluded.

| Endpoint | Result |
| --- | --- |
| GET `/api/notifications/` | Current user's inbox; `unread=true`/`false`, or omit for all |
| GET `/api/notifications/unread-count/` | `{"count": number}` |
| POST `/api/notifications/{notification_id}/read/` | No body; returns the notification; idempotent |
| POST `/api/notifications/read-all/` | No body; `{"updated": number}`; idempotent |
| GET `/api/workspaces/{workspace_id}/activity/` | Accessible workspace history |
| GET `/api/boards/{board_id}/activity/` | Accessible board history |
| GET `/api/cards/{card_id}/activity/` | Accessible card history |

Search and feeds use newest-first pagination:

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

Use `page` and `page_size` (default 30, maximum 100). Existing workspace, board,
list and collaboration collections remain arrays; do not assume every endpoint is paginated.

Notifications use polling. Pause or reduce polling when the page is hidden and
back off on failures. There are no WebSocket, mobile push or scheduled due-date
reminders. Card mutations notify current assignees and the creator, excluding the
actor. Membership mutations notify the owner and the affected user when present
in the response. Access is rechecked when reading, so revoked private-board access
also hides old notifications for that board.

Activity records successful domain API mutations from installation onward, not
authentication or direct ORM/admin changes. `actor` identifies the user; `action`
identifies namespace/route/method; `resource_id` identifies the affected object.
Events do not contain full request bodies or comment text. Notification objects
contain a nested activity and `read_at` (null until read).

## 7. Private file attachments

List metadata: `GET /api/cards/{card_id}/attachments/`.
Upload: POST the same endpoint as multipart/form-data with `file`. Board edit
permission is required. The default maximum is 10 MiB (`ATTACHMENT_MAX_BYTES`).

```javascript
const form = new FormData();
form.append('file', selectedFile);
const attachment = await readJson(await fetch(`/api/cards/${cardId}/attachments/`, {
  method: 'POST', credentials: 'include',
  headers: { Authorization: `Bearer ${access}` }, body: form
}));
```

Do not manually set multipart Content-Type; the browser supplies its boundary.
Handle token expiry before uploading or retry only after a definitive 401.

Download through `GET /api/cards/{card_id}/attachments/{attachment_id}/content/`
with Bearer authentication. Fetch a blob; do not use an unauthenticated public URL.

```javascript
const response = await fetch(
  `/api/cards/${cardId}/attachments/${attachment.id}/content/`,
  { credentials: 'include', headers: { Authorization: `Bearer ${access}` } }
);
if (!response.ok) await readJson(response);
const objectUrl = URL.createObjectURL(await response.blob());
const link = document.createElement('a');
link.href = objectUrl;
link.download = attachment.original_name;
link.click();
setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
```

Downloads are application/octet-stream attachments, not inline executable content.
DELETE `/api/cards/{card_id}/attachments/{attachment_id}/` soft-deletes metadata
and blocks further downloads. Physical blobs remain private under retention policy.

## 8. Errors and deletion

| Status | Frontend behavior |
| --- | --- |
| 400 | Show validation errors; wrong/expired codes and invalid refresh also use this status |
| 401 | Protected API: refresh and retry once; authentication failure: require sign-in |
| 403 | Permission or CSRF failure; do not retry by refreshing access |
| 404 | Missing, deleted or inaccessible object; refresh the UI state |
| 410 | Legacy email-only signup disabled |
| 429 | Respect Retry-After; avoid automatic rapid retries |
| 503 | Code delivery or readiness failure; show a temporary failure state |

Error data can be `{"detail":"..."}`, a mapping of field names to arrays of
messages, or an array of messages. Do not assume every error has `detail`.

DELETE usually returns 204 with no body: do not call response.json() on it.
Domain deletion is soft deletion; deleting a parent makes its descendants inaccessible.
There is no public restore endpoint. This API is not a complete clone of every
Trello feature; build the UI against the operations exposed in OpenAPI.

## 9. Frontend acceptance checks

Before releasing the integrated application, exercise:

1. First OTP login, repeat login, wrong/expired OTP and rate limiting.
2. Page reload, concurrent 401s, expired refresh, CSRF failure and logout.
3. Optional email verification and password flows with session invalidation.
4. Owner/admin/member behavior and private-board denial for another user.
5. Board hydration and drag-and-drop at first/last positions and across lists.
6. Comments, labels, checklist completion and assignee membership handling.
7. Pagination, notification read state and loss of access after membership removal.
8. Upload/download/delete, oversized upload and unauthorized download.
9. Parent deletion, empty collections and 204 handling.

Backend test results do not replace these checks against the actual frontend/browser
and deployment network configuration. Deployment-only work is listed in `operations.md`.
