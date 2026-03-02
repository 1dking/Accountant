
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.config import Settings
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import SendInvoiceSmsRequest, SendSmsRequest, SmsLogResponse

router = APIRouter()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/send", response_model=dict)
async def send_sms(
    data: SendSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_sms(db, data.to, data.message, user, settings)
    return {"data": SmsLogResponse.model_validate(log)}


@router.post("/send-invoice-sms", response_model=dict)
async def send_invoice_sms(
    data: SendInvoiceSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_invoice_sms(db, data.invoice_id, data.to, user, settings)
    return {"data": SmsLogResponse.model_validate(log)}


@router.post("/send-reminder-sms", response_model=dict)
async def send_reminder_sms(
    data: SendInvoiceSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    settings = _get_settings(request)
    log = await service.send_payment_reminder_sms(
        db, data.invoice_id, data.to, user, settings
    )
    return {"data": SmsLogResponse.model_validate(log)}


@router.get("/logs", response_model=dict)
async def list_sms_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
):
    logs, meta = await service.list_sms_logs(db, user.id, pagination)
    return {"data": [SmsLogResponse.model_validate(log) for log in logs], "meta": meta}
