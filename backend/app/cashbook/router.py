"""FastAPI router for the cashbook module."""

import io
import uuid
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.cashbook import service
from app.cashbook.excel_import import parse_excel_file
from app.cashbook.models import CategoryType, EntryType
from app.cashbook.schemas import (
    CashbookEntryCreate,
    CashbookEntryFilter,
    CashbookEntryResponse,
    CashbookEntryUpdate,
    CashbookSummary,
    ImportConfirm,
    ImportPreview,
    PaymentAccountCreate,
    PaymentAccountResponse,
    PaymentAccountUpdate,
    TransactionCategoryCreate,
    TransactionCategoryResponse,
    TransactionCategoryUpdate,
)
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Transaction Category endpoints
# ---------------------------------------------------------------------------


@router.get("/categories")
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    category_type: CategoryType | None = None,
) -> dict:
    """Return all transaction categories. Seeds defaults if none exist."""
    categories = await service.list_categories(db, category_type)
    if not categories:
        await service.seed_default_categories(db)
        categories = await service.list_categories(db, category_type)
    return {"data": [TransactionCategoryResponse.model_validate(c) for c in categories]}


@router.post("/categories", status_code=201)
async def create_category(
    data: TransactionCategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    category = await service.create_category(
        db,
        name=data.name,
        category_type=data.category_type,
        user=current_user,
        color=data.color,
        icon=data.icon,
    )
    return {"data": TransactionCategoryResponse.model_validate(category)}


@router.put("/categories/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    data: TransactionCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    update_data = data.model_dump(exclude_unset=True)
    category = await service.update_category(db, category_id, **update_data)
    return {"data": TransactionCategoryResponse.model_validate(category)}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_category(db, category_id)
    return {"data": {"message": "Category deleted successfully"}}


# ---------------------------------------------------------------------------
# Payment Account endpoints
# ---------------------------------------------------------------------------


@router.get("/accounts")
async def list_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    accounts = await service.list_accounts(db, current_user.id)
    result = []
    for acct in accounts:
        resp = PaymentAccountResponse.model_validate(acct)
        resp.current_balance = await service.get_account_current_balance(db, acct.id)
        result.append(resp)
    return {"data": [r.model_dump(mode="json") for r in result]}


@router.post("/accounts", status_code=201)
async def create_account(
    data: PaymentAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    account = await service.create_account(db, data, current_user)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = account.opening_balance
    return {"data": resp.model_dump(mode="json")}


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    account = await service.get_account(db, account_id)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = await service.get_account_current_balance(db, account_id)
    return {"data": resp.model_dump(mode="json")}


@router.put("/accounts/{account_id}")
async def update_account(
    account_id: uuid.UUID,
    data: PaymentAccountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    account = await service.update_account(db, account_id, data)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = await service.get_account_current_balance(db, account_id)
    return {"data": resp.model_dump(mode="json")}


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_account(db, account_id)
    return {"data": {"message": "Account deactivated successfully"}}


# ---------------------------------------------------------------------------
# Cashbook Entry endpoints
# ---------------------------------------------------------------------------


@router.get("/entries")
async def list_entries(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    account_id: uuid.UUID | None = None,
    entry_type: EntryType | None = None,
    category_id: uuid.UUID | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: str | None = None,
) -> dict:
    filters = CashbookEntryFilter(
        account_id=account_id,
        entry_type=entry_type,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    entries, meta = await service.list_entries(db, filters, pagination)
    return {
        "data": [CashbookEntryResponse.model_validate(e) for e in entries],
        "meta": meta,
    }


@router.post("/entries", status_code=201)
async def create_entry(
    data: CashbookEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    entry = await service.create_entry(db, data, current_user)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    entry = await service.get_entry(db, entry_id)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID,
    data: CashbookEntryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    entry = await service.update_entry(db, entry_id, data, current_user)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    await service.delete_entry(db, entry_id)
    return {"data": {"message": "Entry deleted successfully"}}


# ---------------------------------------------------------------------------
# Summary endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    account_id: uuid.UUID = ...,
    date_from: date = ...,
    date_to: date = ...,
) -> dict:
    summary = await service.get_summary(db, account_id, date_from, date_to)
    return {"data": CashbookSummary(**summary).model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.get("/export/csv")
async def export_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    account_id: uuid.UUID = ...,
    date_from: date = ...,
    date_to: date = ...,
    entry_type: EntryType | None = None,
    category_id: uuid.UUID | None = None,
    search: str | None = None,
) -> StreamingResponse:
    """Export cashbook entries as CSV."""
    from app.cashbook.export import export_cashbook_csv

    filters = CashbookEntryFilter(
        account_id=account_id,
        entry_type=entry_type,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    csv_bytes = await export_cashbook_csv(db, filters)
    filename = f"cashbook_{date_from}_{date_to}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Excel Import endpoints
# ---------------------------------------------------------------------------


@router.post("/import/excel")
async def import_excel_preview(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    file: UploadFile = File(...),
) -> dict:
    """Upload an Excel cashbook file and return a preview of parsed rows."""
    contents = await file.read()
    preview = parse_excel_file(contents)
    return {"data": preview.model_dump(mode="json")}


@router.post("/import/excel/confirm", status_code=201)
async def import_excel_confirm(
    data: ImportConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Confirm and save parsed Excel rows as cashbook entries."""
    # Map category names to IDs
    categories = await service.list_categories(db)
    cat_map = {cat.name: cat.id for cat in categories}

    entries_data = []
    for row in data.rows:
        if row.errors:
            continue
        if row.date is None:
            continue

        category_id = cat_map.get(row.category_name) if row.category_name else None

        entries_data.append({
            "entry_type": row.entry_type.value,
            "date": row.date,
            "description": row.description,
            "total_amount": row.total_amount,
            "tax_amount": row.tax_amount,
            "category_id": category_id,
            "source_id": f"{row.sheet_name}:{row.row_number}",
        })

    entries = await service.bulk_create_entries(
        db, entries_data, data.account_id, current_user
    )
    return {
        "data": {
            "imported_count": len(entries),
            "message": f"Successfully imported {len(entries)} entries.",
        }
    }
