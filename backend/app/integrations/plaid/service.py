
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditAction, AuditResult, safe_record_audit
from app.auth.models import User
from app.config import Settings
from app.core import legal
from app.core.authorization import apply_cashbook_filter
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError, ValidationError

from .models import PlaidConnection, PlaidConsent, PlaidTransaction
from .schemas import CategorizeTransactionRequest, ExchangeTokenRequest, PlaidTransactionFilters


def _get_plaid_client(settings: Settings):
    """Build a Plaid API client from app settings."""
    import plaid
    from plaid.api import plaid_api

    env_map = {
        "sandbox": plaid.Environment.Sandbox,
        "production": plaid.Environment.Production,
    }
    # Plaid removed the deprecated `Development` environment in newer SDK
    # versions; referencing it unconditionally raises AttributeError and breaks
    # the client for EVERY environment. Only include it if this SDK still has it.
    if hasattr(plaid.Environment, "Development"):
        env_map["development"] = plaid.Environment.Development
    configuration = plaid.Configuration(
        host=env_map.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


# ---------------------------------------------------------------------------
# Link token
# ---------------------------------------------------------------------------


def _plaid_country_codes(settings: Settings):
    """Parse `plaid_country_codes` (e.g. "US,CA") into Plaid CountryCode objects.

    Falls back to US if unset/empty so Link always has at least one country.
    """
    from plaid.model.country_code import CountryCode

    raw = getattr(settings, "plaid_country_codes", "") or ""
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
    return [CountryCode(c) for c in codes] or [CountryCode("US")]


async def create_link_token(user: User, settings: Settings) -> str:
    """Create a Plaid Link token so the frontend can open the Plaid Link UI."""
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.link_token_transactions import LinkTokenTransactions
    from plaid.model.products import Products

    client = _get_plaid_client(settings)

    kwargs = dict(
        user=LinkTokenCreateRequestUser(client_user_id=str(user.id)),
        client_name="Accountant",
        products=[Products("transactions")],
        country_codes=_plaid_country_codes(settings),
        language="en",
        # Request up to 24 months of history (730 days is Plaid's hard cap) so
        # the Bank Scanner can backfill toward account creation. This applies to
        # NEW link tokens only — an already-linked item keeps its original
        # window until it is reconnected once.
        transactions=LinkTokenTransactions(days_requested=730),
    )
    # Optionally pin a named Dashboard Link customization (see config note) so
    # Data Transparency Messaging use cases resolve unambiguously.
    customization = (getattr(settings, "plaid_link_customization_name", "") or "").strip()
    if customization:
        kwargs["link_customization_name"] = customization

    request = LinkTokenCreateRequest(**kwargs)
    response = client.link_token_create(request)
    return response["link_token"]


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


async def exchange_public_token(
    db: AsyncSession,
    data: ExchangeTokenRequest,
    user: User,
    settings: Settings,
    ip: str | None = None,
) -> PlaidConnection:
    """Exchange a public token for an access token, encrypt, and store.

    A recorded consent is a HARD precondition: if the user did not acknowledge
    the consent copy, we refuse before contacting Plaid, so no connection is
    created. The consent row and the connection are persisted in the SAME
    transaction — either both land or neither does.
    """
    if not data.consent_acknowledged:
        raise ValidationError(
            "Bank connection requires explicit consent. No connection was created."
        )

    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    client = _get_plaid_client(settings)
    exchange_request = ItemPublicTokenExchangeRequest(public_token=data.public_token)
    response = client.item_public_token_exchange(exchange_request)

    access_token = response["access_token"]
    item_id = response["item_id"]

    encryption = get_encryption_service()
    encrypted_token = encryption.encrypt(access_token)

    # Fetch account details
    accounts_json = await _fetch_accounts(client, access_token)

    connection = PlaidConnection(
        user_id=user.id,
        # Tag the connection with the org when the connector shares the org
        # cashbook, so org peers can see its feed (mirrors get_or_create_bank_account).
        org_id=user.org_id if user.cashbook_access == "org" and user.org_id else None,
        institution_name=data.institution_name,
        institution_id=data.institution_id,
        encrypted_access_token=encrypted_token,
        item_id=item_id,
        is_active=True,
        accounts_json=json.dumps(accounts_json),
    )
    db.add(connection)
    await db.flush()  # assign connection.id without committing yet

    consent = PlaidConsent(
        user_id=user.id,
        tenant_id=str(user.org_id) if user.org_id else None,
        product_scope=legal.PLAID_PRODUCT_SCOPE,
        consent_version=legal.PLAID_CONSENT_VERSION,
        privacy_policy_version=legal.PRIVACY_POLICY_VERSION,
        consent_text=legal.PLAID_CONSENT_TEXT,
        ip_address=ip,
        connection_id=connection.id,
    )
    db.add(consent)

    # Single commit: consent + connection are atomic.
    await db.commit()
    await db.refresh(connection)

    await safe_record_audit(
        db,
        action=AuditAction.PLAID_CONSENT_CAPTURED,
        result=AuditResult.SUCCESS,
        actor_id=user.id,
        actor_email=user.email,
        tenant_id=str(user.org_id) if user.org_id else None,
        resource_type="plaid_connection",
        resource_id=str(connection.id),
        ip_address=ip,
        metadata={
            "consent_version": legal.PLAID_CONSENT_VERSION,
            "privacy_policy_version": legal.PRIVACY_POLICY_VERSION,
            "institution": data.institution_name,
        },
    )
    await safe_record_audit(
        db,
        action=AuditAction.PLAID_CONNECTION_CREATED,
        result=AuditResult.SUCCESS,
        actor_id=user.id,
        actor_email=user.email,
        resource_type="plaid_connection",
        resource_id=str(connection.id),
        ip_address=ip,
    )
    return connection


async def list_consents(
    db: AsyncSession, user_id: uuid.UUID | None = None
) -> list[PlaidConsent]:
    """Consent records, newest first. Platform-admin surface for the
    "provide records on request" obligation. ``user_id`` filters to one user."""
    stmt = select(PlaidConsent).order_by(PlaidConsent.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(PlaidConsent.user_id == user_id)
    return list((await db.execute(stmt)).scalars().all())


async def _fetch_accounts(client, access_token: str) -> list[dict]:
    """Fetch account details from Plaid."""
    from plaid.model.accounts_get_request import AccountsGetRequest

    request = AccountsGetRequest(access_token=access_token)
    response = client.accounts_get(request)
    return [
        {
            "account_id": str(a["account_id"]),
            "name": a["name"],
            "type": str(a["type"]),
            "subtype": str(a.get("subtype", "")),
            "mask": a.get("mask"),
            # Native currency of the account (e.g. "CAD" for a CIBC chequing
            # account) so posted amounts aren't mislabelled USD. May be absent.
            "iso_currency_code": _plaid_account_currency(a),
            # The bank's own current balance, captured for reconciliation
            # (book balance vs bank balance). Refreshed on every sync.
            "current_balance": _plaid_account_current(a),
        }
        for a in response["accounts"]
    ]


def _plaid_account_current(account) -> float | None:
    """Best-effort current balance from a Plaid account (may be None)."""
    try:
        balances = account.get("balances") if hasattr(account, "get") else account["balances"]
        if balances is None:
            return None
        val = balances["current"]
        return float(val) if val is not None else None
    except Exception:
        return None


def _plaid_account_currency(account) -> str | None:
    """Best-effort ISO currency from a Plaid account's balances (may be None)."""
    try:
        balances = account.get("balances") if hasattr(account, "get") else account["balances"]
        if balances is None:
            return None
        return balances["iso_currency_code"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


async def list_connections(
    db: AsyncSession, user: User
) -> list[PlaidConnection]:
    """Connections visible to this user — their own, plus org peers' when they
    share an org cashbook (apply_cashbook_filter on user_id/org_id)."""
    stmt = select(PlaidConnection).order_by(PlaidConnection.created_at.desc())
    stmt = apply_cashbook_filter(stmt, PlaidConnection.user_id, PlaidConnection.org_id, user)
    return list((await db.execute(stmt)).scalars().all())


async def owner_names_for(
    db: AsyncSession, connections: list[PlaidConnection]
) -> dict[uuid.UUID, str]:
    """{user_id: display name} for a set of connections, in one query — so the
    Bank Scanner can label whose bank each row is."""
    ids = {c.user_id for c in connections}
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.full_name, User.email).where(User.id.in_(ids))
    )).all()
    return {r[0]: (r[1] or r[2] or "") for r in rows}


async def get_connection(
    db: AsyncSession, connection_id: uuid.UUID, user_id: uuid.UUID
) -> PlaidConnection:
    """OWNER-ONLY fetch. Used for managing a connection (delete / force-sync,
    which decrypts the access token) — org peers must NOT be able to do those."""
    result = await db.execute(
        select(PlaidConnection).where(
            PlaidConnection.id == connection_id,
            PlaidConnection.user_id == user_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("Plaid connection", str(connection_id))
    return conn


async def get_connection_for_read(
    db: AsyncSession, connection_id: uuid.UUID, user: User
) -> PlaidConnection:
    """Org-aware fetch for READ / categorize (reads institution name, accounts,
    currency). Allows org peers; does NOT permit disconnect/sync (see
    get_connection). Never decrypt the access token through this path."""
    stmt = select(PlaidConnection).where(PlaidConnection.id == connection_id)
    stmt = apply_cashbook_filter(stmt, PlaidConnection.user_id, PlaidConnection.org_id, user)
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if not conn:
        raise NotFoundError("Plaid connection", str(connection_id))
    return conn


async def delete_connection(
    db: AsyncSession, connection_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    conn = await get_connection(db, connection_id, user_id)
    await db.delete(conn)
    await db.commit()


# ---------------------------------------------------------------------------
# Transaction sync
# ---------------------------------------------------------------------------


async def sync_transactions(
    db: AsyncSession,
    connection_id: uuid.UUID,
    user_id: uuid.UUID,
    settings: Settings,
) -> int:
    """Sync transactions using Plaid's /transactions/sync endpoint with cursor."""
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    conn = await get_connection(db, connection_id, user_id)
    encryption = get_encryption_service()
    access_token = encryption.decrypt(conn.encrypted_access_token)
    client = _get_plaid_client(settings)

    cursor = conn.sync_cursor or ""
    added_count = 0
    has_more = True

    while has_more:
        request = TransactionsSyncRequest(
            access_token=access_token,
            cursor=cursor,
        )
        response = client.transactions_sync(request)

        for txn in response.get("added", []):
            # Skip if already exists
            existing = await db.execute(
                select(PlaidTransaction).where(
                    PlaidTransaction.plaid_transaction_id == txn["transaction_id"]
                )
            )
            if existing.scalar_one_or_none():
                continue

            amount = float(txn["amount"])
            # Plaid uses negative for income, positive for expenses
            is_income = amount < 0
            category_list = txn.get("category", [])

            plaid_txn = PlaidTransaction(
                plaid_connection_id=conn.id,
                plaid_transaction_id=txn["transaction_id"],
                account_id=txn["account_id"],
                amount=abs(amount),
                date=txn["date"] if isinstance(txn["date"], date) else date.fromisoformat(str(txn["date"])),
                name=txn.get("name", "")[:500],
                merchant_name=(txn.get("merchant_name") or "")[:255] or None,
                category=", ".join(category_list) if category_list else None,
                pending=txn.get("pending", False),
                is_income=is_income,
                is_categorized=False,
            )
            db.add(plaid_txn)
            added_count += 1

        # Handle removed transactions
        for removed in response.get("removed", []):
            stmt = select(PlaidTransaction).where(
                PlaidTransaction.plaid_transaction_id == removed["transaction_id"]
            )
            result = await db.execute(stmt)
            existing_txn = result.scalar_one_or_none()
            if existing_txn:
                await db.delete(existing_txn)

        cursor = response["next_cursor"]
        has_more = response.get("has_more", False)

    conn.sync_cursor = cursor
    conn.last_sync_at = datetime.now(timezone.utc)
    # Refresh stored account balances (bank truth for reconciliation) — best
    # effort, never let it fail the sync.
    try:
        conn.accounts_json = json.dumps(await _fetch_accounts(client, access_token))
    except Exception:
        pass
    await db.commit()
    return added_count


# ---------------------------------------------------------------------------
# Transaction listing
# ---------------------------------------------------------------------------


async def list_transactions(
    db: AsyncSession,
    user: User,
    filters: PlaidTransactionFilters,
) -> tuple[list[PlaidTransaction], int]:
    """List Plaid transactions with filters. Returns (transactions, total_count).

    Org-scoped: an org member sees every org connection's transactions (their own
    and peers'), via apply_cashbook_filter on the joined PlaidConnection."""
    from sqlalchemy import func

    base = (
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
    )
    base = apply_cashbook_filter(base, PlaidConnection.user_id, PlaidConnection.org_id, user)
    count_base = (
        select(func.count(PlaidTransaction.id))
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
    )
    count_base = apply_cashbook_filter(count_base, PlaidConnection.user_id, PlaidConnection.org_id, user)

    if filters.connection_id:
        base = base.where(PlaidTransaction.plaid_connection_id == filters.connection_id)
        count_base = count_base.where(PlaidTransaction.plaid_connection_id == filters.connection_id)
    if filters.is_categorized is not None:
        base = base.where(PlaidTransaction.is_categorized == filters.is_categorized)
        count_base = count_base.where(PlaidTransaction.is_categorized == filters.is_categorized)
    if filters.is_income is not None:
        base = base.where(PlaidTransaction.is_income == filters.is_income)
        count_base = count_base.where(PlaidTransaction.is_income == filters.is_income)
    if filters.date_from:
        base = base.where(PlaidTransaction.date >= filters.date_from)
        count_base = count_base.where(PlaidTransaction.date >= filters.date_from)
    if filters.date_to:
        base = base.where(PlaidTransaction.date <= filters.date_to)
        count_base = count_base.where(PlaidTransaction.date <= filters.date_to)

    q = (getattr(filters, "search", None) or "").strip().lower()
    if q:
        # name/merchant are encrypted at rest, so there is no SQL LIKE to run —
        # decrypt-filter in Python. Load the SQL-filtered set (ordered), keep the
        # substring matches, then paginate. Fine at the thousands-of-rows scale.
        all_rows = (await db.execute(
            base.order_by(PlaidTransaction.date.desc())
        )).scalars().all()
        matched = [
            t for t in all_rows
            if q in (t.name or "").lower() or q in (t.merchant_name or "").lower()
        ]
        total = len(matched)
        offset = (filters.page - 1) * filters.page_size
        return matched[offset:offset + filters.page_size], total

    total = (await db.execute(count_base)).scalar() or 0
    offset = (filters.page - 1) * filters.page_size
    stmt = base.order_by(PlaidTransaction.date.desc()).offset(offset).limit(filters.page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def bulk_categorize_transactions(
    db: AsyncSession,
    txn_ids: list[uuid.UUID],
    data,
    user: User,
    settings: Settings,
) -> dict:
    """Categorize many transactions at once (e.g. every 'Tim Hortons' →
    Cashbook/Meals). Each posts independently — one failure doesn't abort the
    batch — and re-running is safe (idempotent by plaid_transaction_id)."""
    posted = 0
    errors: list[str] = []
    for tid in txn_ids:
        try:
            await categorize_transaction(
                db, tid,
                CategorizeTransactionRequest(
                    as_type=data.as_type,
                    category_id=data.category_id,
                    entry_type=data.entry_type,
                    confirm_duplicate=data.confirm_duplicate,
                ),
                user, settings,
            )
            posted += 1
        except Exception as e:  # noqa: BLE001 — collect, keep going
            errors.append(str(e)[:120])
            try:
                await db.rollback()
            except Exception:
                pass
    return {"posted": posted, "total": len(txn_ids), "errors": errors}


async def reconciliation_summary(db: AsyncSession, user: User) -> list[dict]:
    """Book balance vs bank balance per connected bank, plus how many synced
    transactions are still un-booked. The "does my book match my bank" view."""
    from decimal import Decimal
    from sqlalchemy import func

    from app.cashbook.models import PaymentAccount
    from app.cashbook.service import get_account_current_balance

    # PaymentAccounts mirrored from Plaid, keyed by plaid_account_id (org-scoped).
    pstmt = select(PaymentAccount).where(
        PaymentAccount.plaid_account_id.isnot(None),
        PaymentAccount.is_active.is_(True),
    )
    pstmt = apply_cashbook_filter(pstmt, PaymentAccount.user_id, PaymentAccount.org_id, user)
    pa_by_pid = {pa.plaid_account_id: pa for pa in (await db.execute(pstmt)).scalars().all()}

    conns = await list_connections(db, user)
    owners = await owner_names_for(db, conns)

    out: list[dict] = []
    for conn in conns:
        try:
            accts_meta = json.loads(conn.accounts_json or "[]")
        except (ValueError, TypeError):
            accts_meta = []

        bank_vals = [a.get("current_balance") for a in accts_meta if a.get("current_balance") is not None]
        bank_balance = sum((Decimal(str(v)) for v in bank_vals), Decimal("0")) if bank_vals else None
        currency = next((a.get("iso_currency_code") for a in accts_meta if a.get("iso_currency_code")), "CAD")

        book_balance = Decimal("0.00")
        matched = False
        for a in accts_meta:
            pa = pa_by_pid.get(a.get("account_id"))
            if pa is not None:
                matched = True
                book_balance += await get_account_current_balance(db, pa.id)

        unbooked = (await db.execute(
            select(func.count(PlaidTransaction.id)).where(
                PlaidTransaction.plaid_connection_id == conn.id,
                PlaidTransaction.is_categorized.is_(False),
            )
        )).scalar() or 0

        diff = (book_balance - bank_balance) if (matched and bank_balance is not None) else None
        reconciled = matched and unbooked == 0 and (bank_balance is None or abs(diff) < Decimal("0.01"))
        out.append({
            "connection_id": str(conn.id),
            "institution_name": conn.institution_name,
            "owner_name": owners.get(conn.user_id),
            "currency": currency,
            "book_balance": str(book_balance) if matched else None,
            "bank_balance": str(bank_balance) if bank_balance is not None else None,
            "difference": str(diff) if diff is not None else None,
            "unbooked_count": int(unbooked),
            "reconciled": bool(reconciled),
            "balance_known": bank_balance is not None,
        })
    return out


# ---------------------------------------------------------------------------
# Bank account provisioning (Plaid account -> Cashbook PaymentAccount)
# ---------------------------------------------------------------------------


def _connection_account_meta(conn: PlaidConnection, plaid_account_id: str) -> dict:
    """The ``accounts_json`` entry for a Plaid account_id ({} if not found)."""
    try:
        accounts = json.loads(conn.accounts_json or "[]")
    except (ValueError, TypeError):
        accounts = []
    for a in accounts:
        if a.get("account_id") == plaid_account_id:
            return a
    return {}


def _connection_currency(conn: PlaidConnection, plaid_account_id: str) -> str:
    """ISO currency for a Plaid account within a connection; CAD if unknown."""
    iso = (_connection_account_meta(conn, plaid_account_id).get("iso_currency_code") or "").strip().upper()
    return iso or "CAD"


async def get_or_create_bank_account(
    db: AsyncSession,
    user: User,
    conn: PlaidConnection,
    plaid_account_id: str,
):
    """Return the PaymentAccount mirroring a Plaid account, creating it once.

    The Cashbook's ``PaymentAccount`` IS the bank-account concept, so posting a
    synced transaction to the Cashbook needs one. We key off ``plaid_account_id``
    so every transaction from the same bank account lands in the same account,
    named e.g. "CIBC Chequing …1234".

    Deliberately does NOT call ``cashbook.create_account``: that sweeps orphan
    (account-less) entries onto the new account, which is wrong here — a bank
    account should only own what we explicitly post to it.
    """
    from app.cashbook.models import AccountType, PaymentAccount

    stmt = select(PaymentAccount).where(PaymentAccount.plaid_account_id == plaid_account_id)
    stmt = apply_cashbook_filter(stmt, PaymentAccount.user_id, PaymentAccount.org_id, user)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    meta = _connection_account_meta(conn, plaid_account_id)
    acct_name = (meta.get("name") or "Account").strip()
    mask = meta.get("mask")
    label = f"{conn.institution_name} {acct_name}".strip()
    if mask:
        label = f"{label} …{mask}"
    label = label[:100]

    org_id = user.org_id if user.cashbook_access == "org" and user.org_id else None
    account = PaymentAccount(
        user_id=user.id,
        org_id=org_id,
        name=label,
        account_type=AccountType.BANK,
        currency=_connection_currency(conn, plaid_account_id),
        opening_balance=0,
        opening_balance_date=date.today(),
        plaid_account_id=plaid_account_id,
    )
    db.add(account)
    await db.flush()  # assign account.id; the caller's create_entry commits it
    return account


# ---------------------------------------------------------------------------
# Transaction categorization
# ---------------------------------------------------------------------------


async def categorize_transaction(
    db: AsyncSession,
    txn_id: uuid.UUID,
    data: CategorizeTransactionRequest,
    user: User,
    settings: Settings,
) -> PlaidTransaction:
    """Categorize a Plaid transaction as expense, income, or ignore.

    Org-scoped: an org peer may categorize a transaction from a shared
    connection (posting it into the shared books). It never disconnects or
    re-syncs the connection, so this uses the read-only org-aware fetch."""
    # Find the transaction — visible if it's the user's own or a shared org one.
    stmt = (
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(PlaidTransaction.id == txn_id)
    )
    stmt = apply_cashbook_filter(stmt, PlaidConnection.user_id, PlaidConnection.org_id, user)
    result = await db.execute(stmt)
    txn = result.scalar_one_or_none()
    if not txn:
        raise NotFoundError("Transaction", str(txn_id))

    # The bank account's native currency (a CIBC chequing account -> "CAD"), so
    # posted amounts aren't mislabelled USD. Also used to name the Cashbook
    # account in the "cashbook" branch below. Read-only org-aware fetch (no
    # token decrypt, no management).
    conn = await get_connection_for_read(db, txn.plaid_connection_id, user)
    currency = _connection_currency(conn, txn.account_id)

    # Tax-integrity guard: refuse to post a second copy of something the user
    # already entered by hand, unless they explicitly confirm. See reconcile.py.
    if data.as_type in ("expense", "income", "cashbook") and not data.confirm_duplicate:
        from app.integrations.plaid.reconcile import (
            PossibleDuplicateError,
            find_duplicate_records,
        )

        dups = await find_duplicate_records(
            db, user, amount=txn.amount, txn_date=txn.date, kind=data.as_type
        )
        if dups:
            raise PossibleDuplicateError(dups)

    if data.as_type == "expense":
        from app.accounting.models import Expense

        expense = Expense(
            user_id=user.id,
            vendor_name=txn.merchant_name or txn.name,
            description=txn.name,
            amount=txn.amount,
            currency=currency,
            date=txn.date,
            category_id=data.expense_category_id,
        )
        db.add(expense)
        await db.flush()
        txn.matched_expense_id = expense.id

    elif data.as_type == "income":
        from app.income.models import Income

        income = Income(
            description=data.description or txn.name,
            amount=txn.amount,
            currency=currency,
            date=txn.date,
            payment_method="bank_transfer",
            created_by=user.id,
        )
        db.add(income)
        await db.flush()
        txn.matched_income_id = income.id

    elif data.as_type == "cashbook":
        # Primary destination: post the bank transaction to the Cashbook against
        # an auto-provisioned account, mirroring the Email Scanner (which posts
        # via the same create_entry). See get_or_create_bank_account.
        from app.cashbook.models import EntryType as _CbEntryType
        from app.cashbook.schemas import CashbookEntryCreate
        from app.cashbook.service import create_entry, get_entry_by_source

        # Idempotency: the same bank transaction must never post twice, even if
        # the button is double-clicked or the row re-categorized.
        existing = await get_entry_by_source(db, "plaid", txn.plaid_transaction_id)
        if existing is not None:
            txn.matched_cashbook_entry_id = existing.id
        else:
            requested = (data.entry_type or "").strip().lower()
            if requested not in ("", "income", "expense"):
                raise ValidationError("entry_type must be 'income' or 'expense'.")
            entry_type = requested or ("income" if txn.is_income else "expense")
            acct = await get_or_create_bank_account(db, user, conn, txn.account_id)
            entry = await create_entry(
                db,
                CashbookEntryCreate(
                    account_id=acct.id,
                    entry_type=_CbEntryType(entry_type),
                    date=txn.date,
                    description=(txn.merchant_name or txn.name or "Bank transaction")[:500],
                    total_amount=txn.amount,
                    category_id=data.category_id,
                    source="plaid",
                    source_id=txn.plaid_transaction_id,
                ),
                user,
            )
            txn.matched_cashbook_entry_id = entry.id

    elif data.as_type == "ignore":
        pass
    else:
        raise ValidationError(f"Invalid type: {data.as_type}. Must be expense, income, or ignore.")

    txn.is_categorized = True
    await db.commit()
    await db.refresh(txn)
    return txn


# ---------------------------------------------------------------------------
# Background sync helper
# ---------------------------------------------------------------------------


async def sync_all_connections(db: AsyncSession, settings: Settings) -> int:
    """Background job: sync transactions for all active Plaid connections."""
    stmt = select(PlaidConnection).where(PlaidConnection.is_active.is_(True))
    result = await db.execute(stmt)
    connections = result.scalars().all()

    total_new = 0
    for conn in connections:
        try:
            count = await sync_transactions(db, conn.id, conn.user_id, settings)
            total_new += count
        except Exception:
            continue

    return total_new
