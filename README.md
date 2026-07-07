# NavaBoard API

A production-minded Django REST API for NavaBoard, an Iranian task management platform inspired by Kanban workflows.

> NavaBoard is being built as an API-first backend. The frontend will communicate with the system through documented REST APIs.

## Project Status

🚧 Under active development.

The first implementation milestone is a secure authentication system with Iranian phone-number OTP login, email/password login, JWT-based sessions, and refresh-token rotation.

## Core Product Goals

- Fast phone-based login using Iranian mobile numbers and SMS OTP
- Automatic account creation after successful first-time OTP verification
- Optional email and password authentication
- Workspace-based collaboration and access control
- Private and workspace-visible boards
- Lists, cards, drag-and-drop ordering, comments, labels, checklists, and attachments
- Production-minded security, documentation, testing, and deployment practices

## Planned Technology Stack

| Area | Technology |
| --- | --- |
| Backend | Django, Django REST Framework |
| Database | PostgreSQL |
| Cache and rate limiting | Redis |
| Background tasks | Celery |
| Authentication | JWT access tokens and refresh-token rotation |
| OTP delivery | Iranian SMS provider |
| File storage | S3-compatible object storage |
| API documentation | OpenAPI / Swagger |
| Testing | Pytest and Django test tools |
| Local development | Docker and Docker Compose |
| CI | GitHub Actions |

## Authentication Design

NavaBoard supports two login methods:

1. **Phone OTP login**
   - Iranian phone numbers are normalized to E.164 format.
   - A six-digit OTP is sent by SMS.
   - A new account is automatically created after successful verification when the phone number does not already exist.

2. **Email and password login**
   - Users may add a verified email address and password later from profile settings.
   - Each email address and phone number belongs to exactly one account.

## Security Principles

- OTP values are hashed before storage.
- OTPs expire after two minutes.
- OTP verification attempts are limited.
- OTP requests are rate-limited by phone number and IP address.
- Access tokens are short-lived.
- Refresh tokens are stored in HttpOnly Secure cookies and can be revoked.
- Sensitive configuration is stored in environment variables and never committed to Git.
- Production traffic must use HTTPS.

## Roadmap

- [x] Product analysis and architecture design
- [x] Database and domain modeling
- [x] Authentication flow design
- [ ] Repository and documentation foundation
- [ ] Django project infrastructure
- [ ] Authentication and OTP module
- [ ] Workspace and permission module
- [ ] Board, list, and card module
- [ ] Card collaboration features
- [ ] Automated tests, Swagger, CI, and deployment

## Documentation

Architecture diagrams, security decisions, database models, and implementation planning will be maintained under the `docs/` directory.

## Development Workflow

- Feature branches are created from `main`.
- Each change is committed using Conventional Commits.
- Changes are reviewed through pull requests before merging into `main`.
- Secrets, API keys, `.env` files, and local databases must never be committed.

## License

This project is licensed under the MIT License.