
import json
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import Response
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
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    settings: Settings = request.app.state.settings
    await service.delete_phone_number(db, phone_id, settings)
    return {"data": {"message": "Phone number deleted"}}


@router.get("/my-number")
async def get_my_number(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get the current user's assigned Twilio number, or null if unassigned."""
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.assigned_user_id == user.id)
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        return {"data": None}
    return {
        "data": {
            "id": str(phone.id),
            "phone_number": phone.phone_number,
            "friendly_name": phone.friendly_name,
        }
    }


# ---------------------------------------------------------------------------
# Voice — Twilio webhooks (signed by Twilio, NOT by our JWT auth)
# ---------------------------------------------------------------------------


async def verified_twilio_form(request: Request) -> dict:
    """Verify Twilio webhook signature and return the parsed form params.

    Twilio signs every webhook with HMAC-SHA1 of the full URL + sorted form
    params, keyed by our account auth_token. If signature is missing or
    invalid → 403. If auth_token isn't configured server-side, we can't
    validate, so also reject (we'd rather refuse to serve than accept
    unsigned webhooks).

    Returns a plain {name: str} dict of the form body — handlers downstream
    can't call request.form() again (starlette won't let you read the body
    twice), so we hand the parsed params over.
    """
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}

    settings: Settings = request.app.state.settings
    if not settings.twilio_auth_token:
        raise HTTPException(
            status_code=403,
            detail="Twilio webhook signature verification unavailable — server misconfigured",
        )

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    # When Cloudflare proxies HTTPS, the URL FastAPI reconstructs depends on
    # X-Forwarded-Proto. uvicorn + nginx/Apache reverse proxy normally honor
    # the header; if signature validation fails we'll see it in tests.
    url = str(request.url)

    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params


def _xml_response(twiml_body: str) -> Response:
    """Wrap a TwiML XML body in a FastAPI Response with the right content type."""
    return Response(content=twiml_body, media_type="application/xml")


@router.post("/voice/twiml")
async def voice_twiml(
    form: Annotated[dict, Depends(verified_twilio_form)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Outbound webhook: Twilio hits this when a browser Client places a call.

    The browser SDK passes `params: { To: '+1...' }` to device.connect(); that
    gets forwarded to this webhook. We look up the dialing user's assigned
    Twilio number (from the `client:<uuid>` From identity) and use it as
    callerId so the called party sees the right number, not "Twilio default".
    """
    from twilio.twiml.voice_response import VoiceResponse, Dial

    to_number = form.get("To", "")
    from_identity = form.get("From", "")  # "client:<user_uuid>" when initiated from browser

    # Strip "client:" prefix if present, parse UUID, look up assigned number
    caller_id: str | None = None
    if from_identity.startswith("client:"):
        identity_str = from_identity[len("client:") :]
        try:
            user_uuid = uuid.UUID(identity_str)
            result = await db.execute(
                select(TwilioPhoneNumber).where(
                    TwilioPhoneNumber.assigned_user_id == user_uuid
                )
            )
            phone = result.scalar_one_or_none()
            if phone:
                caller_id = phone.phone_number
        except ValueError:
            pass  # malformed UUID, fall through to global

    # Fall back to the global TWILIO_FROM_NUMBER if user has no assigned number
    if not caller_id:
        settings: Settings = request.app.state.settings
        caller_id = settings.twilio_from_number or None

    response = VoiceResponse()
    dial_kwargs: dict = {"record": "record-from-answer-dual"}
    if caller_id:
        dial_kwargs["caller_id"] = caller_id
    dial = Dial(**dial_kwargs)
    dial.number(to_number)
    response.append(dial)
    return _xml_response(str(response))


@router.post("/voice/incoming")
async def voice_incoming(
    form: Annotated[dict, Depends(verified_twilio_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Inbound webhook: Twilio hits this when one of our owned numbers is called.

    Looks up the TwilioPhoneNumber by `Called` (the digit the caller dialed),
    finds the assigned user, and rings their browser Client identity for 10s.
    If the browser doesn't pick up, the `action` URL fires the fallback handler
    which rings the user's cell.
    """
    from twilio.twiml.voice_response import VoiceResponse, Dial

    called = form.get("Called", "")

    # Find owner of this number
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == called)
    )
    phone = result.scalar_one_or_none()

    response = VoiceResponse()
    if phone is None or phone.assigned_user_id is None:
        # No assigned recipient — say goodbye gracefully
        response.say("Sorry, this number is not currently assigned. Please try again later.")
        return _xml_response(str(response))

    # Dial the browser client; on timeout/no-answer, Twilio POSTs to action URL
    dial = Dial(
        timeout=10,
        action="https://accountant.ocidm.io/api/communication/voice/incoming-fallback",
        record="record-from-answer-dual",
    )
    dial.client(str(phone.assigned_user_id))
    response.append(dial)
    return _xml_response(str(response))


@router.post("/voice/incoming-fallback")
async def voice_incoming_fallback(
    form: Annotated[dict, Depends(verified_twilio_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Fires after the browser-Dial finishes (success or timeout).

    If DialCallStatus == 'completed', the browser answered — return empty so
    Twilio hangs up cleanly. Otherwise, ring the assigned user's fallback_phone
    (cell) using the called Twilio number as callerId.
    """
    from twilio.twiml.voice_response import VoiceResponse, Dial

    dial_status = form.get("DialCallStatus", "")
    called = form.get("Called", "") or form.get("To", "")  # 'Called' on incoming; 'To' on the fallback POST

    if dial_status == "completed":
        return _xml_response("<Response/>")

    # Look up the assigned user and their fallback_phone
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == called)
    )
    phone = result.scalar_one_or_none()

    response = VoiceResponse()
    if phone is None or phone.assigned_user_id is None:
        response.say("Sorry, no one is available to take your call. Please try again later.")
        return _xml_response(str(response))

    user_result = await db.execute(select(User).where(User.id == phone.assigned_user_id))
    assigned_user = user_result.scalar_one_or_none()
    fallback = getattr(assigned_user, "fallback_phone", None) if assigned_user else None

    if not fallback:
        response.say("Sorry, no one is available to take your call. Please try again later.")
        return _xml_response(str(response))

    dial = Dial(timeout=20, caller_id=called)
    dial.number(fallback)
    response.append(dial)
    return _xml_response(str(response))


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
    sms_enabled: bool = True,
):
    """Search for available Twilio phone numbers to purchase."""
    from app.kyc.models import KycStatus, KycVerification

    settings: Settings = request.app.state.settings

    # Check KYC status
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()
    if settings.twilio_kyc_required and (
        not kyc or kyc.status != KycStatus.APPROVED.value
    ):
        raise ForbiddenError(
            "KYC verification must be approved before purchasing phone numbers."
        )

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ForbiddenError("Twilio is not configured.")

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    kwargs: dict = {"limit": 10, "sms_enabled": sms_enabled}
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
                    # Twilio REST API returns "SMS"/"MMS" uppercase, "voice" lowercase.
                    # Fall back to lowercase to defend against a future casing change.
                    "sms": n.capabilities.get("SMS", n.capabilities.get("sms", False)),
                    "mms": n.capabilities.get("MMS", n.capabilities.get("mms", False)),
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
    """Purchase a Twilio phone number. Requires admin role; KYC gate behind TWILIO_KYC_REQUIRED."""
    from app.kyc.models import KycStatus, KycVerification

    settings: Settings = request.app.state.settings

    # Check KYC
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()
    if settings.twilio_kyc_required and (
        not kyc or kyc.status != KycStatus.APPROVED.value
    ):
        raise ForbiddenError(
            "KYC verification must be approved before purchasing."
        )

    phone_number = body.get("phone_number")
    if not phone_number:
        raise ValidationError("phone_number is required.")

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
    result = await service.get_capability_token(db, current_user, settings)
    return {"data": CapabilityTokenResponse(token=result["token"], identity=result["identity"])}


# Also expose as GET — frontend SDK initialization fetches via GET by convention,
# and we want clients with React Query to be able to use a simple GET hook.
@router.get("/calls/capability-token")
async def get_capability_token_get(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = request.app.state.settings
    result = await service.get_capability_token(db, current_user, settings)
    return {"data": CapabilityTokenResponse(token=result["token"], identity=result["identity"])}


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
