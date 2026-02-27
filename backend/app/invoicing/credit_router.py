"""FastAPI router for credit notes and refunds."""


import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role
from app.invoicing import credit_service
from app.invoicing.credit_schemas import (
    ContactCreditBalance,
    CreditNoteCreate,
    CreditNoteListItem,
    CreditNoteResponse,
)

router = APIRouter()


@router.get("/credit-notes")
async def list_credit_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    invoice_id: uuid.UUID | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
) -> dict:
    """List credit notes, optionally filtered by invoice or contact."""
    notes = await credit_service.list_credit_notes(db, invoice_id, contact_id)
    return {"data": [CreditNoteListItem.model_validate(cn) for cn in notes]}


@router.post("/{invoice_id}/credit-note", status_code=201)
async def create_credit_note(
    invoice_id: uuid.UUID,
    data: CreditNoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a credit note against an invoice."""
    credit_note = await credit_service.create_credit_note(
        db,
        invoice_id=invoice_id,
        amount=data.amount,
        issue_date=data.issue_date,
        user=current_user,
        reason=data.reason,
    )
    return {"data": CreditNoteResponse.model_validate(credit_note)}


@router.get("/credit-notes/{credit_note_id}")
async def get_credit_note(
    credit_note_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single credit note by ID."""
    credit_note = await credit_service.get_credit_note(db, credit_note_id)
    return {"data": CreditNoteResponse.model_validate(credit_note)}


@router.post("/credit-notes/{credit_note_id}/apply")
async def apply_credit_note(
    credit_note_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Apply a credit note, reducing the invoice balance."""
    credit_note = await credit_service.apply_credit_note(
        db, credit_note_id, current_user
    )
    return {"data": CreditNoteResponse.model_validate(credit_note)}


@router.get("/credit-notes/contact/{contact_id}/balance")
async def get_contact_credit_balance(
    contact_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get the credit balance summary for a contact."""
    balance = await credit_service.get_contact_credit_balance(db, contact_id)
    return {"data": ContactCreditBalance(**balance)}
