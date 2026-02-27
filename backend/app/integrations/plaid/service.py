from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import Settings
from app.core.encryption import get_encryption_service
from app.core.exceptions import NotFoundError, ValidationError

from .models import PlaidConnection, PlaidTransaction
from .schemas import CategorizeTransactionRequest, ExchangeTokenRequest, PlaidTransactionFilters


def _get_plaid_client(settings: Settings):
    """Build a Plaid API client from app settings."""
    import plaid
    from plaid.api import plaid_api

    env_map = {
        "sandbox": plaid.Environment.Sandbox,
        "development": plaid.Environment.Development,
        "production": plaid.Environment.Production,
    }
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


async def create_link_token(user: User, settings: Settings) -> str:
    """Create a Plaid Link token so the frontend can open the Plaid Link UI."""
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.country_code import CountryCode
    from plaid.model.products import Products

    client = _get_plaid_client(settings)

    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user.id)),
        client_name="Accountant",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
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
) -> PlaidConnection:
    """Exchange a public token for an access token, encrypt, and store."""
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
        institution_name=data.institution_name,
        institution_id=data.institution_id,
        encrypted_access_token=encrypted_token,
        item_id=item_id,
        is_active=True,
        accounts_json=json.dumps(accounts_json),
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


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
        }
        for a in response["accounts"]
    ]


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


async def list_connections(
    db: AsyncSession, user_id: uuid.UUID
) -> list[PlaidConnection]:
    result = await db.execute(
        select(PlaidConnection)
        .where(PlaidConnection.user_id == user_id)
        .order_by(PlaidConnection.created_at.desc())
    )
    return list(result.scalars().all())


async def get_connection(
    db: AsyncSession, connection_id: uuid.UUID, user_id: uuid.UUID
) -> PlaidConnection:
    result = await db.execute(
        select(PlaidConnection).where(
            PlaidConnection.id == connection_id,
            PlaidConnection.user_id == user_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("Plaid connection not found")
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
    await db.commit()
    return added_count


# ---------------------------------------------------------------------------
# Transaction listing
# ---------------------------------------------------------------------------


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    filters: PlaidTransactionFilters,
) -> tuple[list[PlaidTransaction], int]:
    """List Plaid transactions with filters. Returns (transactions, total_count)."""
    from sqlalchemy import func

    base = (
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(PlaidConnection.user_id == user_id)
    )
    count_base = (
        select(func.count(PlaidTransaction.id))
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(PlaidConnection.user_id == user_id)
    )

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

    total = (await db.execute(count_base)).scalar() or 0
    offset = (filters.page - 1) * filters.page_size
    stmt = base.order_by(PlaidTransaction.date.desc()).offset(offset).limit(filters.page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


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
    """Categorize a Plaid transaction as expense, income, or ignore."""
    # Find the transaction ensuring it belongs to this user
    stmt = (
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(PlaidTransaction.id == txn_id, PlaidConnection.user_id == user.id)
    )
    result = await db.execute(stmt)
    txn = result.scalar_one_or_none()
    if not txn:
        raise NotFoundError("Transaction not found")

    if data.as_type == "expense":
        from app.accounting.models import Expense

        expense = Expense(
            user_id=user.id,
            vendor_name=txn.merchant_name or txn.name,
            description=txn.name,
            amount=txn.amount,
            currency="USD",
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
            currency="USD",
            date=txn.date,
            payment_method="bank_transfer",
            created_by=user.id,
        )
        db.add(income)
        await db.flush()
        txn.matched_income_id = income.id

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
