# Access Control Reference

Role-based access control (RBAC) implementation for the Accountant platform.

## Role Hierarchy

| Role | Staff? | Description |
|------|--------|-------------|
| `admin` | yes | Full system access, user management, destructive operations |
| `team_member` | yes | Create/read/update business records. Cannot delete (admin only) |
| `accountant` | yes | Financial operations, document management, client interactions |
| `viewer` | yes | Read-only access to business records and reports |
| `client` | **no** | Portal user. An outsider, scoped to their own contact |

## The two access layers

**1. Route layer — what a role may DO.** `require_role([...])` on the endpoint.
This is where "a viewer can't create", "a team member can't delete", and "a
client is refused" are enforced.

**2. Service layer — which RECORDS a user may touch.** Two different checks,
and picking the wrong one is a security bug:

| Helper | Use for | Rule |
|--------|---------|------|
| `authorize_shared` / `apply_shared_filter` | **Shared business records**: contacts, invoices, estimates, proposals, income, expenses, budgets, recurring, tasks | Any **staff** role may reach them. Non-staff (`client`) must own the record. |
| `authorize_owner` / `apply_ownership_filter` | **Private resources**: Drive documents, meetings, SMTP configs (which hold encrypted credentials) | Only the creator, or an admin. |
| `authorize_cashbook_owner` / `apply_cashbook_filter` | Cashbook | Org-scoped when `cashbook_access == "org"`, else personal. |

Staff share one book of business. Requiring **ownership on top of** the role
matrix is a bug, not extra safety: a `viewer` creates nothing, so an ownership
gate means it can see nothing — the role becomes useless by construction — and
two team members cannot see each other's contacts, which defeats a shared CRM.

### Why `client` must never be in `STAFF_ROLES`

The contacts list/get endpoints are gated by `get_current_user`, **not**
`require_role` — so any authenticated user, `client` included, reaches the
service layer. The shared/owner filter is therefore the *only* thing standing
between a portal user and the entire contact book. Because `client` is not
staff, it falls back to the owner filter and sees nothing. Adding `client` to
`STAFF_ROLES` would expose every contact, invoice and proposal to every portal
user. See `tests/integration/test_permission_model.py`.

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
