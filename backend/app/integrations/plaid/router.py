
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mfa_common import has_mfa
from app.auth.models import Role, User
from app.config import Settings
from app.core import legal
from app.core.authorization import apply_cashbook_filter
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    BulkCategorizeRequest,
    CategorizeTransactionRequest,
    CreateLinkTokenResponse,
    ExchangeTokenRequest,
    PlaidConnectionResponse,
    PlaidConsentResponse,
    PlaidLinkConfigResponse,
    PlaidTransactionFilters,
    PlaidTransactionResponse,
)

router = APIRouter()

_LINK_ROLES = (Role.ACCOUNTANT, Role.ADMIN)


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _link_allowlist(settings: Settings) -> set[str]:
    raw = getattr(settings, "plaid_link_allowed_emails", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _passes_link_allowlist(user: User, settings: Settings) -> bool:
    """Operator-only pilot gate. An EMPTY allow-list means 'any accountant/admin'
    (the documented go-public state); a non-empty one restricts Link to exactly
    those emails — which is what keeps self-serve tenant admins out."""
    allow = _link_allowlist(settings)
    return (not allow) or (user.email or "").lower() in allow


def _is_plaid_config_manager(user: User, settings: Settings) -> bool:
    """Who may SEE and EDIT the platform Plaid keys — a single designated
    manager (``plaid_config_manager_email``). Distinct from the Link allow-list,
    which governs who can CONNECT a bank (kept open to all operators). If the
    manager email is unset, fall back to the allow-list so nothing breaks before
    it's configured."""
    mgr = (getattr(settings, "plaid_config_manager_email", "") or "").strip().lower()
    if not mgr:
        return _passes_link_allowlist(user, settings)
    return (user.email or "").lower() == mgr


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def require_financial_data_access(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """A second factor is required to READ consumer financial data.

    Previously MFA only gated *creating* a bank connection, so an account with a
    password-only login could still read the transactions it produced. This closes
    that gap — either factor (passkey or authenticator app) satisfies it.

    LOCKOUT SAFETY, by design:
      * This gates ONLY the Plaid data endpoints. The login flow is untouched, so
        you can always sign in and use the rest of the application.
      * The 403 carries code=MFA_REQUIRED so the UI can route to enrollment rather
        than dead-ending.
      * Set PLAID_REQUIRE_MFA_FOR_DATA=false and restart to lift the gate entirely
        without a code change.
    """
    settings = _get_settings(request)
    if not getattr(settings, "plaid_require_mfa_for_data", True):
        return user
    if not await has_mfa(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MFA_REQUIRED",
                "message": (
                    "Set up two-factor authentication (a passkey or an authenticator "
                    "app) to view bank data. Your other sections are unaffected."
                ),
            },
        )
    return user


async def require_plaid_link_access(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Hard gate in front of the Plaid Link flow.

    Three conditions, all required: the ``plaid_link_enabled`` flag is on (kept
    OFF until consent + MFA + privacy policy are verified), the caller holds an
    accountant/admin role, and the caller has MFA — EITHER TOTP or a passkey
    (they are interchangeable, so a TOTP-only user keeps access). Consent itself
    is enforced at exchange time in the service.
    """
    settings = _get_settings(request)
    if not getattr(settings, "plaid_link_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAID_LINK_DISABLED",
                "message": "Bank connections are not enabled yet.",
            },
        )
    if user.role not in _LINK_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    if not _passes_link_allowlist(user, settings):
        # Non-allowlisted account (incl. self-serve tenant admins) — refused
        # while the pilot allow-list is set.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAID_LINK_NOT_ALLOWLISTED",
                "message": "Bank connections are limited to specific operator accounts.",
            },
        )
    if not await has_mfa(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MFA_REQUIRED",
                "message": "Enable two-factor authentication (an authenticator app or a passkey) before connecting a bank account.",
            },
        )
    return user


# ---------------------------------------------------------------------------
# Link configuration — drives whether the frontend surfaces the Connect button
# ---------------------------------------------------------------------------


@router.get("/link-config", response_model=dict)
async def get_link_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = _get_settings(request)
    base = settings.public_base_url.rstrip("/")
    mfa_ok = await has_mfa(db, user)
    enabled = (
        bool(getattr(settings, "plaid_link_enabled", False))
        and mfa_ok
        and user.role in _LINK_ROLES
        and _passes_link_allowlist(user, settings)
    )
    cfg = PlaidLinkConfigResponse(
        enabled=enabled,
        mfa_required=True,
        mfa_satisfied=mfa_ok,
        consent_required=True,
        consent_text=legal.PLAID_CONSENT_TEXT,
        consent_version=legal.PLAID_CONSENT_VERSION,
        privacy_policy_version=legal.PRIVACY_POLICY_VERSION,
        privacy_policy_url=f"{base}/privacy",
        terms_url=f"{base}/terms",
    )
    return {"data": cfg}


# ---------------------------------------------------------------------------
# Plaid Link
# ---------------------------------------------------------------------------


@router.post("/link-token", response_model=dict)
async def create_link_token(
    request: Request,
    user: User = Depends(require_plaid_link_access),
):
    settings = _get_settings(request)
    link_token = await service.create_link_token(user, settings)
    return {"data": CreateLinkTokenResponse(link_token=link_token)}


@router.post("/exchange-token", response_model=dict)
async def exchange_public_token(
    data: ExchangeTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_plaid_link_access),
):
    settings = _get_settings(request)
    connection = await service.exchange_public_token(
        db, data, user, settings, ip=_client_ip(request)
    )
    return {"data": _connection_response(connection)}


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


@router.get("/connections", response_model=dict)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_financial_data_access),
):
    connections = await service.list_connections(db, user)
    owner_names = await service.owner_names_for(db, connections)
    return {"data": [_connection_response(c, owner_names.get(c.user_id)) for c in connections]}


@router.delete("/connections/{connection_id}", response_model=dict)
async def delete_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
    _mfa: User = Depends(require_financial_data_access),
):
    await service.delete_connection(db, connection_id, user.id)
    return {"data": {"detail": "Plaid connection removed"}}


@router.post("/connections/{connection_id}/sync", response_model=dict)
async def sync_transactions(
    connection_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
    _mfa: User = Depends(require_financial_data_access),
):
    settings = _get_settings(request)
    count = await service.sync_transactions(db, connection_id, user.id, settings)
    return {"data": {"detail": f"Synced {count} new transactions"}}


# ---------------------------------------------------------------------------
# Consent records — platform-admin surface for "provide records on request"
# ---------------------------------------------------------------------------


@router.get("/admin/consents", response_model=dict)
async def list_consents_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
):
    # Platform-admin gate (admin role or SUPER_ADMIN_EMAILS).
    from app.platform_admin.router import require_platform_admin

    await require_platform_admin(request, current_user)
    consents = await service.list_consents(db, user_id=user_id)
    return {"data": [PlaidConsentResponse.model_validate(c) for c in consents]}


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


@router.get("/transactions", response_model=dict)
async def list_transactions(
    request: Request,
    connection_id: uuid.UUID | None = None,
    is_categorized: bool | None = None,
    is_income: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_financial_data_access),
):
    from datetime import date as date_type

    filters = PlaidTransactionFilters(
        connection_id=connection_id,
        is_categorized=is_categorized,
        is_income=is_income,
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        search=search,
        page=page,
        page_size=page_size,
    )
    transactions, total = await service.list_transactions(db, user, filters)
    return {
        "data": [PlaidTransactionResponse.model_validate(t) for t in transactions],
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.post("/transactions/{txn_id}/categorize", response_model=dict)
async def categorize_transaction(
    txn_id: uuid.UUID,
    data: CategorizeTransactionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
    _mfa: User = Depends(require_financial_data_access),
):
    settings = _get_settings(request)
    txn = await service.categorize_transaction(db, txn_id, data, user, settings)
    return {"data": PlaidTransactionResponse.model_validate(txn)}


@router.post("/transactions/bulk-categorize", response_model=dict)
async def bulk_categorize_transactions(
    data: BulkCategorizeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
    _mfa: User = Depends(require_financial_data_access),
):
    """Post many reviewed transactions to the Cashbook at once — e.g. after
    searching a payee name and selecting them all."""
    settings = _get_settings(request)
    result = await service.bulk_categorize_transactions(db, data.txn_ids, data, user, settings)
    return {"data": result}


@router.get("/transactions/{txn_id}/possible-duplicates", response_model=dict)
async def transaction_possible_duplicates(
    txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_financial_data_access),
):
    """Manual Expense/Income rows that likely match this Plaid transaction, so the
    review UI can warn before the user categorizes it into the books."""
    from app.integrations.plaid.models import PlaidConnection, PlaidTransaction
    from app.integrations.plaid.reconcile import find_duplicate_records

    stmt = (
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(PlaidTransaction.id == txn_id)
    )
    stmt = apply_cashbook_filter(stmt, PlaidConnection.user_id, PlaidConnection.org_id, user)
    txn = (await db.execute(stmt)).scalar_one_or_none()
    if not txn:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Transaction", str(txn_id))

    candidates = await find_duplicate_records(
        db, user, amount=txn.amount, txn_date=txn.date, kind="expense"
    ) + await find_duplicate_records(
        db, user, amount=txn.amount, txn_date=txn.date, kind="income"
    )
    return {"data": {"possible_duplicates": candidates}}


@router.get("/reconciliation", response_model=dict)
async def reconciliation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_financial_data_access),
):
    """Per-bank book balance vs bank balance + un-booked count."""
    return {"data": await service.reconciliation_summary(db, user)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connection_response(conn: object, owner_name: str | None = None) -> PlaidConnectionResponse:
    import json as json_mod

    resp = PlaidConnectionResponse.model_validate(conn)
    resp.owner_name = owner_name  # whose bank this is (for org-shared views)
    # Parse accounts_json if present
    raw = getattr(conn, "accounts_json", None)
    if raw:
        try:
            resp.accounts = json_mod.loads(raw)
        except (json_mod.JSONDecodeError, TypeError):
            resp.accounts = None
    return resp
