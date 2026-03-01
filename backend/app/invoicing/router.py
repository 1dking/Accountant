
import uuid
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role
from app.invoicing import service
from app.invoicing.models import InvoiceStatus
from app.invoicing.pdf import generate_invoice_pdf
from app.public.models import ResourceType
from app.public.service import create_public_token, revoke_token
from app.invoicing.schemas import (
    InvoiceCreate,
    InvoiceFilter,
    InvoiceListItem,
    InvoicePaymentCreate,
    InvoicePaymentResponse,
    InvoiceResponse,
    InvoiceUpdate,
)

router = APIRouter()


@router.get("")
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    status: InvoiceStatus | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
) -> dict:
    filters = InvoiceFilter(
        search=search, status=status, contact_id=contact_id,
        date_from=date_from, date_to=date_to,
    )
    invoices, meta = await service.list_invoices(db, filters, pagination)
    return {"data": [InvoiceListItem.model_validate(inv) for inv in invoices], "meta": meta}


@router.get("/stats")
async def invoice_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    stats = await service.get_invoice_stats(db)
    return {"data": stats}


@router.post("", status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    invoice = await service.create_invoice(db, data, current_user)
    return {"data": InvoiceResponse.model_validate(invoice)}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    invoice = await service.get_invoice(db, invoice_id)
    return {"data": InvoiceResponse.model_validate(invoice)}


@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    invoice = await service.update_invoice(db, invoice_id, data, current_user)
    return {"data": InvoiceResponse.model_validate(invoice)}


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_invoice(db, invoice_id)
    return {"data": {"message": "Invoice deleted"}}


@router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    invoice = await service.send_invoice(db, invoice_id)
    return {"data": InvoiceResponse.model_validate(invoice)}


@router.post("/{invoice_id}/payments", status_code=201)
async def record_payment(
    invoice_id: uuid.UUID,
    data: InvoicePaymentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    payment = await service.record_payment(db, invoice_id, data, current_user)
    return {"data": InvoicePaymentResponse.model_validate(payment)}


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Response:
    invoice = await service.get_invoice(db, invoice_id)
    pdf_bytes = generate_invoice_pdf(invoice)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice-{invoice.invoice_number}.pdf"'
        },
    )


@router.post("/{invoice_id}/share", status_code=201)
async def share_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a shareable public link for an invoice."""
    await service.get_invoice(db, invoice_id)
    token = await create_public_token(db, ResourceType.INVOICE, invoice_id, current_user)
    base_url = str(request.base_url).rstrip("/")
    shareable_url = f"{base_url}/p/{token.token}"
    return {"data": {"id": str(token.id), "token": token.token, "resource_type": "invoice", "resource_id": str(invoice_id), "shareable_url": shareable_url}}


@router.delete("/{invoice_id}/share/{token_id}")
async def revoke_invoice_share(
    invoice_id: uuid.UUID,
    token_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Revoke a shareable link for an invoice."""
    await revoke_token(db, token_id, current_user)
    return {"data": {"message": "Share link revoked"}}
