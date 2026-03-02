# Access Control Reference

Role-based access control (RBAC) implementation for the Accountant platform.

## Role Hierarchy

| Role | Level | Description |
|------|-------|-------------|
| `admin` | Highest | Full system access, user management, destructive operations |
| `accountant` | Standard | Financial operations, document management, client interactions |
| `viewer` | Lowest | Read-only access to documents and reports |

## Authentication Flow

1. User sends `POST /api/auth/login` with email + password
2. Backend verifies credentials, returns JWT access token
3. All subsequent requests include `Authorization: Bearer <token>`
4. `get_current_user` dependency decodes token, loads user from DB
5. If token is expired or invalid, returns 401 Unauthorized

## Authorization Dependencies

```python
# Any authenticated user
@router.get("/resource")
async def get_resource(
    current_user: Annotated[User, Depends(get_current_user)],
):

# Specific roles only
@router.post("/resource")
async def create_resource(
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.ACCOUNTANT]))],
):

# Admin only
@router.delete("/resource/{id}")
async def delete_resource(
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
):
```

## Endpoint Permission Matrix

| Operation | Admin | Accountant | Viewer | Public |
|-----------|-------|------------|--------|--------|
| View documents | Y | Y | Y | N |
| Upload documents | Y | Y | N | N |
| Delete documents | Y | N | N | N |
| Create invoices | Y | Y | N | N |
| Delete invoices | Y | N | N | N |
| Record payments | Y | Y | N | N |
| View reports | Y | Y | Y | N |
| Manage users | Y | N | N | N |
| Update settings | Y | Y | N | N |
| Delete recordings | Y | Y | N | N |
| View shared docs | - | - | - | Y (via token) |
| Pay invoices | - | - | - | Y (via token) |
| Health check | - | - | - | Y |

## Public Access (No Auth)

Endpoints accessible without authentication:

- `GET /api/system/health` — liveness probe
- `GET /api/system/stats` — application metrics
- `POST /api/auth/login` — login
- `POST /api/auth/register` — registration
- `GET /api/public/view/{token}` — shared document view
- `POST /api/public/view/{token}/accept` — accept estimate
- `POST /api/public/view/{token}/pay` — pay invoice
- `GET /api/settings/company/logo` — company logo image
- `GET /api/meetings/guest/{token}` — guest meeting info
- `POST /api/meetings/guest/{token}/join` — guest join meeting

## Token Query Parameter

Some endpoints accept `?token=` for browser contexts where headers can't be set:

```python
# Used for img src, video src, download links
async def get_current_user_or_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)] = None,
    token: str | None = Query(None),
):
```

## Sensitive Data Protection

- Passwords: bcrypt hashed, never stored or returned in plaintext
- API keys: stored in `.env`, never in code or database
- SMTP passwords: Fernet-encrypted in database
- Integration tokens: Fernet-encrypted in database
- JWT secret: environment variable, rotated periodically
