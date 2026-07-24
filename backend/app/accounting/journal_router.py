"""FastAPI router for manual journal entries."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import journal_service
from app.accounting.journal_schemas import (
    JournalEntryCreate,
    JournalEntryResponse,
    JournalLineResponse,
)
from app.accounting.ledger_models import JournalEntry
from app.auth.models import User
from app.dependencies import get_current_user, get_db

router = APIRouter()


def _to_response(entry: JournalEntry) -> JournalEntryResponse:
    lines = [
        JournalLineResponse(
            id=ln.id,
            account_id=ln.account_id,
            account_code=ln.account.code if ln.account else None,
            account_name=ln.account.name if ln.account else None,
            debit=ln.debit,
            credit=ln.credit,
            description=ln.description,
        )
        for ln in entry.lines
    ]
    total = sum((ln.debit for ln in entry.lines), Decimal("0"))
    return JournalEntryResponse(
        id=entry.id,
        entry_number=entry.entry_number,
        date=entry.date,
        memo=entry.memo,
        source=entry.source,
        source_id=entry.source_id,
        status=entry.status,
        created_by=entry.created_by,
        created_at=entry.created_at,
        lines=lines,
        total=total,
    )


@router.get("/journal")
async def list_journal_entries(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
    include_void: bool = True,
) -> dict:
    entries = await journal_service.list_entries(
        db, user, date_from=date_from, date_to=date_to, include_void=include_void
    )
    return {"data": [_to_response(e) for e in entries]}


@router.post("/journal", status_code=201)
async def create_journal_entry(
    data: JournalEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    entry = await journal_service.create_entry(db, data, user)
    return {"data": _to_response(entry)}


@router.get("/journal/{entry_id}")
async def get_journal_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    entry = await journal_service.get_entry(db, entry_id, user)
    return {"data": _to_response(entry)}


@router.post("/journal/{entry_id}/void")
async def void_journal_entry(
    entry_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    entry = await journal_service.void_entry(db, entry_id, user)
    return {"data": _to_response(entry)}
