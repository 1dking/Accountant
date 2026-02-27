
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    CategorizeTransactionRequest,
    CreateLinkTokenResponse,
    ExchangeTokenRequest,
    PlaidConnectionResponse,
    PlaidTransactionFilters,
    PlaidTransactionResponse,
)

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Plaid Link
# ---------------------------------------------------------------------------


@router.post("/link-token", response_model=dict)
async def create_link_token(
    request: Request,
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    link_token = await service.create_link_token(user, settings)
    return {"data": CreateLinkTokenResponse(link_token=link_token)}


@router.post("/exchange-token", response_model=dict)
async def exchange_public_token(
    data: ExchangeTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    connection = await service.exchange_public_token(db, data, user, settings)
    return {"data": _connection_response(connection)}


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


@router.get("/connections", response_model=dict)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    connections = await service.list_connections(db, user.id)
    return {"data": [_connection_response(c) for c in connections]}


@router.delete("/connections/{connection_id}", response_model=dict)
async def delete_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.delete_connection(db, connection_id, user.id)
    return {"data": {"detail": "Plaid connection removed"}}


@router.post("/connections/{connection_id}/sync", response_model=dict)
async def sync_transactions(
    connection_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    count = await service.sync_transactions(db, connection_id, user.id, settings)
    return {"data": {"detail": f"Synced {count} new transactions"}}


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
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import date as date_type

    filters = PlaidTransactionFilters(
        connection_id=connection_id,
        is_categorized=is_categorized,
        is_income=is_income,
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        page=page,
        page_size=page_size,
    )
    transactions, total = await service.list_transactions(db, user.id, filters)
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
):
    settings = _get_settings(request)
    txn = await service.categorize_transaction(db, txn_id, data, user, settings)
    return {"data": PlaidTransactionResponse.model_validate(txn)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connection_response(conn: object) -> PlaidConnectionResponse:
    import json as json_mod

    resp = PlaidConnectionResponse.model_validate(conn)
    # Parse accounts_json if present
    raw = getattr(conn, "accounts_json", None)
    if raw:
        try:
            resp.accounts = json_mod.loads(raw)
        except (json_mod.JSONDecodeError, TypeError):
            resp.accounts = None
    return resp
