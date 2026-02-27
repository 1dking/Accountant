from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import (
    SendInvoiceEmailRequest,
    SendReminderEmailRequest,
    SmtpConfigCreate,
    SmtpConfigResponse,
    SmtpConfigUpdate,
    TestEmailRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# SMTP Config CRUD
# ---------------------------------------------------------------------------


@router.post("/configs", response_model=dict)
async def create_smtp_config(
    data: SmtpConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    config = await service.create_smtp_config(db, data, user)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.get("/configs", response_model=dict)
async def list_smtp_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    configs = await service.list_smtp_configs(db, user)
    return {
        "data": [SmtpConfigResponse.model_validate(c) for c in configs],
    }


@router.get("/configs/{config_id}", response_model=dict)
async def get_smtp_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    config = await service.get_smtp_config(db, config_id)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.put("/configs/{config_id}", response_model=dict)
async def update_smtp_config(
    config_id: uuid.UUID,
    data: SmtpConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    config = await service.update_smtp_config(db, config_id, data)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.delete("/configs/{config_id}", response_model=dict)
async def delete_smtp_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    await service.delete_smtp_config(db, config_id)
    return {"data": {"detail": "SMTP config deleted"}}


# ---------------------------------------------------------------------------
# Email actions
# ---------------------------------------------------------------------------


@router.post("/test", response_model=dict)
async def send_test_email(
    data: TestEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    from datetime import datetime, timezone

    smtp_config = await service.get_smtp_config(db, data.smtp_config_id)
    html_body = service.render_template(
        "test_email.html",
        company_name=smtp_config.from_name,
        year=datetime.now(timezone.utc).year,
    )

    await service.send_email(
        smtp_config,
        to=data.to_email,
        subject="Test Email — Accountant",
        html_body=html_body,
    )
    return {"data": {"detail": f"Test email sent to {data.to_email}"}}


@router.post("/send-invoice", response_model=dict)
async def send_invoice_email(
    data: SendInvoiceEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    result = await service.send_invoice_email(
        db=db,
        invoice_id=data.invoice_id,
        smtp_config_id=data.smtp_config_id,
        recipient_email=data.recipient_email,
        subject=data.subject,
        message=data.message,
        user=user,
    )
    return {"data": result}


@router.post("/send-reminder", response_model=dict)
async def send_payment_reminder(
    data: SendReminderEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    result = await service.send_payment_reminder(
        db=db,
        invoice_id=data.invoice_id,
        smtp_config_id=data.smtp_config_id,
        user=user,
    )
    return {"data": result}
