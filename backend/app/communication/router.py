
import json
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.communication import service
from app.communication.models import TwilioPhoneNumber
from app.communication.schemas import (
    CallLogCreate,
    CallLogResponse,
    CapabilityTokenResponse,
    LiveChatMessageCreate,
    LiveChatMessageResponse,
    LiveChatSessionCreate,
    LiveChatSessionResponse,
    SmsMessageCreate,
    SmsMessageResponse,
    TwilioPhoneNumberCreate,
    TwilioPhoneNumberResponse,
    TwilioPhoneNumberUpdate,
)
from app.config import Settings
from app.core.exceptions import ForbiddenError, ValidationError
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# STATIC / PUBLIC PATHS FIRST
# ---------------------------------------------------------------------------


@router.post("/sms/webhook")
async def sms_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Twilio SMS webhook - no auth required. Receives incoming SMS."""
    form_data = await request.form()
    from_number = str(form_data.get("From", ""))
    to_number = str(form_data.get("To", ""))
    body = str(form_data.get("Body", ""))
    twilio_sid = str(form_data.get("MessageSid", ""))

    sms = await service.receive_sms(db, from_number, to_number, body, twilio_sid)
    # Return TwiML empty response (Twilio expects XML)
    return {"data": {"message": "OK"}}


@router.post("/calls/missed-webhook")
async def missed_call_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Twilio missed call webhook - no auth required."""
    settings = request.app.state.settings
    form_data = await request.form()
    from_number = str(form_data.get("From", ""))
    to_number = str(form_data.get("To", ""))

    call = await service.handle_missed_call(db, from_number, to_number, settings)
    return {"data": {"message": "OK"}}


@router.post("/chat/widget/init", status_code=201)
async def init_chat_widget(
    data: LiveChatSessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public endpoint for initializing a chat widget session (no auth)."""
    session = await service.create_session(db, data)
    return {"data": LiveChatSessionResponse.model_validate(session)}


@router.post("/sms/send")
async def send_sms(
    data: SmsMessageCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    settings = request.app.state.settings
    sms = await service.send_sms(db, current_user, data.to_number, data.body, settings)
    return {"data": SmsMessageResponse.model_validate(sms)}


@router.get("/sms")
async def list_sms(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    contact_id: uuid.UUID | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    messages, total = await service.list_sms_messages(
        db, contact_id=contact_id, user_id=user_id, page=page, page_size=page_size
    )
    return {
        "data": [SmsMessageResponse.model_validate(m) for m in messages],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# Phone Numbers
# ---------------------------------------------------------------------------


@router.get("/phone-numbers")
async def list_phone_numbers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    numbers = await service.list_phone_numbers(db)
    return {"data": [TwilioPhoneNumberResponse.model_validate(n) for n in numbers]}


@router.post("/phone-numbers", status_code=201)
async def add_phone_number(
    data: TwilioPhoneNumberCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    phone = await service.add_phone_number(db, data)
    return {"data": TwilioPhoneNumberResponse.model_validate(phone)}


@router.put("/phone-numbers/{phone_id}/assign")
async def assign_phone_number(
    phone_id: uuid.UUID,
    data: TwilioPhoneNumberUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    phone = await service.assign_phone_number(db, phone_id, data.assigned_user_id)
    return {"data": TwilioPhoneNumberResponse.model_validate(phone)}


@router.delete("/phone-numbers/{phone_id}")
async def delete_phone_number(
    phone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_phone_number(db, phone_id)
    return {"data": {"message": "Phone number deleted"}}


# ---------------------------------------------------------------------------
# Twilio Number Search & Purchase (requires KYC approval)
# ---------------------------------------------------------------------------


@router.get("/twilio/available-numbers")
async def search_available_numbers(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    area_code: str | None = None,
    country: str = "US",
    contains: str | None = None,
):
    """Search for available Twilio phone numbers to purchase."""
    from app.kyc.models import KycStatus, KycVerification

    # Check KYC status
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc or kyc.status != KycStatus.APPROVED:
        raise ForbiddenError(
            "KYC verification must be approved before purchasing phone numbers."
        )

    settings: Settings = request.app.state.settings
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ForbiddenError("Twilio is not configured.")

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    kwargs: dict = {"limit": 10}
    if area_code:
        kwargs["area_code"] = area_code
    if contains:
        kwargs["contains"] = contains

    numbers = client.available_phone_numbers(country).local.list(**kwargs)

    return {
        "data": [
            {
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name,
                "locality": n.locality,
                "region": n.region,
                "capabilities": {
                    "voice": n.capabilities.get("voice", False),
                    "sms": n.capabilities.get("sms", False),
                    "mms": n.capabilities.get("mms", False),
                },
            }
            for n in numbers
        ]
    }


@router.post("/twilio/purchase")
async def purchase_number(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role([Role.ADMIN]))],
    body: dict,
):
    """Purchase a Twilio phone number. Requires admin role and approved KYC."""
    from app.kyc.models import KycStatus, KycVerification

    # Check KYC
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc or kyc.status != KycStatus.APPROVED:
        raise ForbiddenError(
            "KYC verification must be approved before purchasing."
        )

    phone_number = body.get("phone_number")
    if not phone_number:
        raise ValidationError("phone_number is required.")

    settings: Settings = request.app.state.settings
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ForbiddenError("Twilio is not configured.")

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    try:
        purchased = client.incoming_phone_numbers.create(
            phone_number=phone_number
        )
    except Exception as e:
        raise ValidationError(f"Failed to purchase number: {str(e)[:200]}")

    # Save to DB using the existing TwilioPhoneNumber model.
    # Store the Twilio SID and capabilities in the capabilities_json column.
    capabilities_data = json.dumps({"sid": purchased.sid})

    phone = TwilioPhoneNumber(
        id=uuid.uuid4(),
        phone_number=purchased.phone_number,
        friendly_name=purchased.friendly_name or phone_number,
        capabilities_json=capabilities_data,
    )
    db.add(phone)
    await db.commit()
    await db.refresh(phone)

    return {
        "data": {
            "id": str(phone.id),
            "phone_number": phone.phone_number,
            "friendly_name": phone.friendly_name,
            "sid": purchased.sid,
        }
    }


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@router.post("/calls/log", status_code=201)
async def log_call(
    data: CallLogCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER]))],
) -> dict:
    call = await service.create_call_log(db, data, current_user)
    return {"data": CallLogResponse.model_validate(call)}


@router.get("/calls")
async def list_calls(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    contact_id: uuid.UUID | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    calls, total = await service.list_call_logs(
        db, contact_id=contact_id, user_id=user_id, page=page, page_size=page_size
    )
    return {
        "data": [CallLogResponse.model_validate(c) for c in calls],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/calls/capability-token")
async def get_capability_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = request.app.state.settings
    token = await service.get_capability_token(db, current_user, settings)
    return {"data": CapabilityTokenResponse(token=token)}


# ---------------------------------------------------------------------------
# Live Chat
# ---------------------------------------------------------------------------


@router.post("/chat/sessions", status_code=201)
async def create_chat_session(
    data: LiveChatSessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    session = await service.create_session(db, data)
    return {"data": LiveChatSessionResponse.model_validate(session)}


@router.get("/chat/sessions")
async def list_chat_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> dict:
    sessions, total = await service.list_sessions(
        db, status=status, page=page, page_size=page_size
    )
    return {
        "data": [LiveChatSessionResponse.model_validate(s) for s in sessions],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/chat/sessions/{session_id}/messages", status_code=201)
async def send_chat_message(
    session_id: uuid.UUID,
    data: LiveChatMessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    message = await service.send_message(db, session_id, data, current_user)
    return {"data": LiveChatMessageResponse.model_validate(message)}


@router.get("/chat/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    messages, total = await service.get_session_messages(
        db, session_id, page=page, page_size=page_size
    )
    return {
        "data": [LiveChatMessageResponse.model_validate(m) for m in messages],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        },
    }


@router.post("/chat/sessions/{session_id}/close")
async def close_chat_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    session = await service.close_session(db, session_id)
    return {"data": LiveChatSessionResponse.model_validate(session)}
