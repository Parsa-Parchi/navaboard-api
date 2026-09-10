# Operations

Keep `.env` private. Development SMS/email delivery remains configurable and no
external provider is activated by these changes. Production needs:

- Unique long `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, explicit `DJANGO_ALLOWED_HOSTS`.
- PostgreSQL `DATABASE_URL`, a dedicated application role and tested backups.
- Shared Redis `CACHE_URL` for multi-worker throttling; correct `DRF_NUM_PROXIES` for trusted proxies.
- HTTPS, `AUTH_REFRESH_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`.
- Same-origin frontend/API proxy by default. Separate origins require a CORS allowlist at the proxy and `CSRF_TRUSTED_ORIGINS`. Cross-site cookies also require SameSite=None/Secure and browser support.
- Persistent private `MEDIA_ROOT`; never expose it publicly. Apply proxy upload size limits as well as `ATTACHMENT_MAX_BYTES`.
- SMTP backend/credentials when activating email verification.
- When ready: `SMS_PROVIDER=smsir`, API key, template ID, code parameter and timeout. Console mode does not deliver real SMS.

`DJANGO_DEBUG` is parsed as a boolean. Development code flags are forced off when
settings load with debug disabled. Keep `AUTH_ENABLE_EMAIL_SIGNUP=False`.

## Release checks

```text
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yml --validate --fail-on-warn
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Serve `config.wsgi:application` with your production WSGI server behind HTTPS;
`runserver` is development only. Serve `STATIC_ROOT` through the web server.
Review deployment checks for redirects/HSTS and proxy-specific settings. This
repository does not assume control of TLS termination or trust forwarded headers.
`/health/` checks database readiness without exposing connection details.

## Retention and maintenance

Schedule `python manage.py flushexpiredtokens` daily. Monitor HTTP errors, database,
cache, storage and provider failures; verify backup restoration.

Activity/in-app notifications persist in PostgreSQL and cover successful HTTP
domain mutations from installation onward, not direct ORM/admin changes. No worker
is needed for polling. Scheduled deadline reminders, WebSockets and mobile push
are not implemented. Deleted attachment blobs remain in private storage for an
operator-defined retention/backup policy. Apply scanning/quotas if required by your
product's upload policy. Do not blindly purge retained objects needed for recovery.

## Frontend coordination

- Initialize CSRF and send `X-CSRFToken` for login/refresh/logout.
- Email-only signup is disabled by default and hidden from Swagger.
- Deleted ancestors are consistently inaccessible.
- New feeds/search use pagination; existing collections retain arrays.
- Refresh ignores stale Bearer headers and serializes rotation per session.

See [Frontend integration guide](frontend-integration.md) for request sequences and examples.
