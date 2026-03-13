"""FastAPI router for the cashbook module."""

import io
import uuid
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.cashbook import service
from app.cashbook.excel_import import parse_excel_file
from app.cashbook.models import CategoryType, EntryStatus, EntryType
from app.cashbook.schemas import (
    AccountDeleteRequest,
    BulkCategorizeRequest,
    BulkDeleteRequest,
    BulkMoveAccountRequest,
    BulkStatusRequest,
    CashbookCaptureResponse,
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
    SplitTransactionRequest,
    TransactionCategoryCreate,
    TransactionCategoryResponse,
    TransactionCategoryUpdate,
)
from app.core.idempotency import IdempotencyResult, require_idempotency_key
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role
from app.documents.storage import LocalStorage, StorageBackend

router = APIRouter()


def get_storage(request: Request) -> StorageBackend:
    """Resolve the storage backend from application settings."""
    settings = request.app.state.settings
    return LocalStorage(settings.storage_path)


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
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    accounts = await service.list_accounts(db, current_user)
    balances = await service.get_account_balances_batch(db, [a.id for a in accounts])
    result = []
    for acct in accounts:
        resp = PaymentAccountResponse.model_validate(acct)
        resp.current_balance = balances.get(acct.id, acct.opening_balance)
        result.append(resp)
    return {"data": [r.model_dump(mode="json") for r in result]}


@router.post("/accounts", status_code=201)
async def create_account(
    data: PaymentAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    account = await service.create_account(db, data, current_user)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = account.opening_balance
    return {"data": resp.model_dump(mode="json")}


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    account = await service.get_account(db, account_id, current_user)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = await service.get_account_current_balance(db, account_id)
    return {"data": resp.model_dump(mode="json")}


@router.put("/accounts/{account_id}")
async def update_account(
    account_id: uuid.UUID,
    data: PaymentAccountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    account = await service.update_account(db, account_id, data, current_user)
    resp = PaymentAccountResponse.model_validate(account)
    resp.current_balance = await service.get_account_current_balance(db, account_id)
    return {"data": resp.model_dump(mode="json")}


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_account(db, account_id, current_user)
    return {"data": {"message": "Account deactivated successfully"}}


@router.post("/accounts/{account_id}/delete")
async def delete_account_with_entries(
    account_id: uuid.UUID,
    data: AccountDeleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    result = await service.delete_account_with_entries(
        db, account_id, data.action, data.target_account_id, current_user,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Cashbook Entry by-source lookup
# ---------------------------------------------------------------------------


@router.get("/entries/by-source")
async def get_entry_by_source(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    source: str = ...,
    source_id: str = ...,
) -> dict:
    """Look up a cashbook entry by source (e.g. source=expense&source_id=<uuid>).

    Returns the entry with its payment account info, or null if not booked.
    """
    entry = await service.get_entry_by_source(db, source, source_id)
    if entry is None:
        return {"data": None}
    resp = CashbookEntryResponse.model_validate(entry)
    account_name = entry.account.name if entry.account else None
    return {
        "data": {
            **resp.model_dump(mode="json"),
            "account_name": account_name,
        }
    }


# ---------------------------------------------------------------------------
# Cashbook Entry endpoints
# ---------------------------------------------------------------------------


@router.get("/entries")
async def list_entries(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    account_id: uuid.UUID | None = None,
    entry_type: EntryType | None = None,
    category_id: uuid.UUID | None = None,
    status: EntryStatus | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: str | None = None,
    include_deleted: bool = False,
) -> dict:
    filters = CashbookEntryFilter(
        account_id=account_id,
        entry_type=entry_type,
        category_id=category_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        include_deleted=include_deleted,
    )
    entries, meta = await service.list_entries(db, filters, pagination, current_user)
    return {
        "data": [CashbookEntryResponse.model_validate(e) for e in entries],
        "meta": meta,
    }


@router.post("/entries", status_code=201)
async def create_entry(
    data: CashbookEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    idempotency: Annotated[IdempotencyResult, Depends(require_idempotency_key)],
) -> dict:
    if idempotency.cached_response is not None:
        return idempotency.cached_response
    entry = await service.create_entry(db, data, current_user)
    result = {"data": CashbookEntryResponse.model_validate(entry)}
    await idempotency.save(result, status_code=201)
    return result


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    entry = await service.get_entry(db, entry_id, current_user)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID,
    data: CashbookEntryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    entry = await service.update_entry(db, entry_id, data, current_user)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    await service.delete_entry(db, entry_id, current_user)
    return {"data": {"message": "Entry deleted successfully"}}


@router.post("/entries/{entry_id}/restore")
async def restore_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    entry = await service.restore_entry(db, entry_id, current_user)
    return {"data": CashbookEntryResponse.model_validate(entry)}


@router.post("/entries/{entry_id}/split")
async def split_entry(
    entry_id: uuid.UUID,
    data: SplitTransactionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    children = await service.split_entry(db, entry_id, data.lines, current_user)
    return {"data": [CashbookEntryResponse.model_validate(c) for c in children]}


# ---------------------------------------------------------------------------
# Orphan fix
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Trash endpoints
# ---------------------------------------------------------------------------


@router.get("/trash")
async def list_trash(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    """List all soft-deleted entries and deactivated accounts."""
    entries, accounts, meta = await service.list_trash(db, current_user, pagination)
    return {
        "data": {
            "entries": [CashbookEntryResponse.model_validate(e) for e in entries],
            "accounts": [PaymentAccountResponse.model_validate(a) for a in accounts],
        },
        "meta": meta,
    }


@router.get("/trash/count")
async def trash_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    counts = await service.trash_count(db, current_user)
    return {"data": counts}


@router.post("/trash/empty")
async def empty_trash(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    result = await service.empty_trash(db, current_user)
    return {"data": result}


@router.post("/trash/restore-all")
async def restore_all_trash(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    result = await service.restore_all_trash(db, current_user)
    return {"data": result}


@router.post("/entries/{entry_id}/permanent-delete")
async def permanent_delete_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    await service.permanent_delete_entry(db, entry_id, current_user)
    return {"data": {"message": "Entry permanently deleted"}}


@router.post("/accounts/{account_id}/restore")
async def restore_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    account = await service.restore_account(db, account_id, current_user)
    return {"data": PaymentAccountResponse.model_validate(account)}


@router.post("/accounts/{account_id}/permanent-delete")
async def permanent_delete_account(
    account_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    await service.permanent_delete_account(db, account_id, current_user)
    return {"data": {"message": "Account permanently deleted"}}


# ---------------------------------------------------------------------------
# Orphan fix
# ---------------------------------------------------------------------------


@router.post("/entries/fix-orphans")
async def fix_orphan_entries(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    count = await service.fix_orphan_entries(db, current_user)
    return {"data": {"reassigned": count}}


# ---------------------------------------------------------------------------
# Bulk action endpoints
# ---------------------------------------------------------------------------


@router.post("/entries/bulk-delete")
async def bulk_delete_entries(
    data: BulkDeleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    count = await service.bulk_soft_delete(db, data.entry_ids, current_user)
    return {"data": {"deleted": count}}


@router.post("/entries/bulk-categorize")
async def bulk_categorize_entries(
    data: BulkCategorizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    count = await service.bulk_categorize(db, data.entry_ids, data.category_id, current_user)
    return {"data": {"updated": count}}


@router.post("/entries/bulk-move")
async def bulk_move_entries(
    data: BulkMoveAccountRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    count = await service.bulk_move_account(db, data.entry_ids, data.account_id, current_user)
    return {"data": {"moved": count}}


@router.post("/entries/bulk-status")
async def bulk_update_status(
    data: BulkStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
) -> dict:
    count = await service.bulk_update_status(db, data.entry_ids, data.status, current_user)
    return {"data": {"updated": count}}


# ---------------------------------------------------------------------------
# Capture (upload-and-book) endpoint
# ---------------------------------------------------------------------------


@router.post("/capture", status_code=201)
async def capture_endpoint(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    file: UploadFile = File(...),
    entry_type: EntryType = ...,
    account_id: uuid.UUID = ...,
    folder_id: uuid.UUID | None = None,
) -> dict:
    """Upload a document, run AI extraction, and create a cashbook entry.

    Chains upload -> sync AI extraction -> cashbook entry creation.
    Each step is independent: if AI fails the document is still saved,
    if entry creation fails the document + extraction are still saved.
    """
    file_data = await file.read()
    settings = request.app.state.settings

    document, extraction, entry, elapsed_ms = await service.capture_and_book(
        db=db,
        storage=storage,
        file_data=file_data,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        user=current_user,
        settings=settings,
        entry_type=entry_type,
        account_id=account_id,
        folder_id=folder_id,
    )

    return {
        "data": CashbookCaptureResponse(
            document_id=document.id,
            document_title=document.title or document.original_filename,
            entry_id=entry.id if entry else None,
            entry_type=entry.entry_type if entry else None,
            entry_amount=entry.total_amount if entry else None,
            entry_description=entry.description if entry else None,
            entry_date=str(entry.date) if entry else None,
            category_name=None,
            extraction=extraction,
            processing_time_ms=elapsed_ms,
        )
    }


# ---------------------------------------------------------------------------
# Summary endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = ...,
    date_to: date = ...,
    account_id: Optional[uuid.UUID] = None,
) -> dict:
    if account_id is not None:
        summary = await service.get_summary(db, account_id, date_from, date_to)
    else:
        summary = await service.get_aggregate_summary(db, current_user, date_from, date_to)
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
    _: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT]))],
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
