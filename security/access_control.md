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

## Records are private to their owner

**Every employee has their own section.** Two people working the phones must not
see each other's contacts. Only an **admin** (the agency owner) sees across
everyone. A colleague gets a record only when it is **explicitly shared** with
them — sharing is an action, never a default.

## The three access layers

Keep these separate. Conflating "which records can I see" with "which sections
can I open" is what produced a data-sharing bug once already.

| Layer | Question | Mechanism |
|-------|----------|-----------|
| **Module access** | *Can I open the Cashbook section at all?* | `User.feature_access_json` → `resolve_feature_access()` (`app/auth/features.py`) |
| **Record visibility** | *Which records inside it are mine to see?* | `authorize_owner` / `apply_ownership_filter` |
| **Action rights** | *May I create / delete?* | `require_role([...])` on the route |

| Helper | Use for | Rule |
|--------|---------|------|
| `authorize_owner` / `apply_ownership_filter` | All business records: contacts, invoices, estimates, proposals, income, expenses, budgets, recurring, tasks — and private resources: Drive documents, meetings, SMTP configs | Only the creator, or an admin. |
| `authorize_cashbook_owner` / `apply_cashbook_filter` | Cashbook | Org-scoped when `cashbook_access == "org"`, else personal. |

Ownership checks raise **404, not 403**. A 403 confirms the record exists, which
leaks the shape of a colleague's book to anyone probing ids.

### Do not "fix" the viewer role by loosening ownership

A `viewer` owns nothing, so by default it sees nothing. **That is intended.** A
viewer sees exactly what has been shared with it. This exact reasoning ("the
viewer role is useless, ownership must be too strict") once led to business
records being shared across all staff — the opposite of what the business wants.
The tests asserting a viewer could read any contact were **wrong and were
rewritten**. See `tests/integration/test_permission_model.py`.

### The contacts list is guarded by the filter alone

The contacts list/get endpoints are gated by `get_current_user`, **not**
`require_role` — so any authenticated user, `client` included, reaches the
service layer. `apply_ownership_filter` is therefore the *only* thing standing
between a portal user and the entire contact book. It returns **200 with an empty
list**, not 403 — so tests must assert on the **data**, not the status code.

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
