# Security

Security policies, access controls, and validation patterns for the Accountant platform.

## Files

| File | Purpose |
|------|---------|
| `policies.yaml` | Authentication, authorization, rate limiting, data classification |
| `input_validation.md` | Input validation patterns and examples |
| `access_control.md` | Role hierarchy, endpoint permissions, token management |

## Existing Security Controls

| Control | Implementation |
|---------|---------------|
| Authentication | JWT tokens via `python-jose` |
| Password hashing | bcrypt via `passlib` |
| Authorization | Role-based (admin, accountant, viewer) via `require_role()` |
| Encryption | Fernet symmetric encryption for sensitive data |
| Input validation | Pydantic v2 schemas on all endpoints |
| SQL injection | SQLAlchemy ORM (no raw SQL) |
| File upload | Extension allowlisting, size limits |
| CORS | Configured in FastAPI middleware |

## Reporting Security Issues

If you discover a security vulnerability, do not commit a fix publicly. Contact the project owner directly.
