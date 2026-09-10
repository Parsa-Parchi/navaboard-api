# NavaBoard API

Django REST backend for a Trello-style Kanban application. Python 3.13,
Django 5.2, PostgreSQL, DRF, SimpleJWT and drf-spectacular.

## Features

- Phone OTP registration/login; optional verified email/password added afterward.
- Access tokens in JSON; rotating refresh tokens in HttpOnly cookies; CSRF protection.
- Workspaces, ownership transfer, roles and owner-only workspace deletion.
- Private/workspace-visible boards, board membership, ordered lists/cards and deadlines.
- Labels, checklists/items, comments, assignees and private file attachments.
- Paginated card search, activity history and persistent in-app notifications.
- Current permissions and soft-deleted parents checked when reading data and notifications.
- Swagger with endpoint-specific permissions, schemas and authentication examples.

## Local development (PowerShell)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements/base.txt
Copy-Item .env.example .env
# Configure PostgreSQL DATABASE_URL and a unique DJANGO_SECRET_KEY in .env.
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Keep an existing `.env` without overwriting it. PostgreSQL must already be running.
The database role needs permission to create a test database for tests.
SMS/email console backends support local development without activating providers.

- Swagger: `/api/docs/`
- OpenAPI: `/api/schema/` (exported copy: `schema.yml`)
- Database readiness: `/health/`
- [Frontend integration guide](docs/frontend-integration.md)
- [Operations and deployment](docs/operations.md)

## Verification

```powershell
.venv\Scripts\python.exe manage.py test --noinput
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py spectacular --file schema.yml --validate --fail-on-warn
.venv\Scripts\python.exe manage.py check
```

CI runs checks against PostgreSQL. New feeds/search have pagination envelopes;
existing board/workspace/collaboration collections retain array responses.

## Authentication contract

Only phone OTP creates accounts by default. Legacy email-only signup routes return
410 and are hidden from Swagger. Leave `AUTH_ENABLE_EMAIL_SIGNUP=False`.

Refresh is sent through `Set-Cookie`, never JSON. The frontend includes credentials,
keeps access in memory and sends `Authorization: Bearer <access>`. Initialize
`/api/auth/csrf/` and send `X-CSRFToken` on login, refresh and logout. JavaScript
does not read or create the HttpOnly refresh cookie. See the frontend guide.

## Scope

Notifications are an in-app polling inbox, not WebSocket, mobile push or scheduled
deadline reminders. History records successful domain API mutations from installation
onward; direct ORM/admin edits and authentication operations are not included.
Attachments use private server storage and authenticated downloads; deleted blobs
are retained for an operator-defined retention/backup policy.

Production still needs environment configuration, HTTPS, a shared cache, backups
and actual SMS/email credentials. No infrastructure is deployed by this repository.
Never serve `private-media/` publicly.

## License

MIT; see `LICENSE`.
