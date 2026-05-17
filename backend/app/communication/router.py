
import json
import logging
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.communication import service
from app.communication.models import CallLog, TwilioPhoneNumber
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
from app.dependencies import get_current_user, get_current_user_or_token, get_db, require_role

logger = logging.getLogger(__name__)

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
    # Reconstruct the URL Twilio actually signed (public HTTPS), NOT the
    # internal URL uvicorn sees (http://0.0.0.0:8000/...). Twilio signs the
    # exact public URL it POSTs to; the HMAC fails if either scheme or host
    # differs by even one character. Cloudflare/Apache set X-Forwarded-Proto
    # and X-Forwarded-Host; fall back to the raw request only for local dev.
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.hostname
        or ""
    )
    url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"

    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params


def _xml_response(twiml_body: str) -> Response:
    """Wrap a TwiML XML body in a FastAPI Response with the right content type."""
    return Response(content=twiml_body, media_type="application/xml")


def _voicemail_response(user: "User | None") -> Response:
    """TwiML for the voicemail capture flow.

    Branches on the user's voicemail_greeting_type:
      - 'audio' + storage_key → <Play> the user's R2-stored greeting via
        our proxy endpoint
      - 'text' + text → <Say> the user's wording (Polly.Joanna), then
        auto-append the mechanical "leave a message after the beep" line
      - else / type='audio' but key NULL → fall back to default Polly.Joanna
        first-name prompt (defensive: better than silence)

    Total custom-greeting + record + close should stay under ~8s of
    spoken content. Reused from BOTH /voice/incoming-fallback (no-cell
    branch) AND /voice/voicemail (cell-failed branch).
    """
    from twilio.twiml.voice_response import VoiceResponse, Record

    response = VoiceResponse()
    used_custom = False
    if user is not None:
        gtype = getattr(user, "voicemail_greeting_type", None)
        if gtype == "audio":
            key = getattr(user, "voicemail_greeting_storage_key", None)
            if key:
                response.play(
                    f"https://accountant.ocidm.io/api/communication/voicemail-greeting/{user.id}.mp3"
                )
                used_custom = True
            else:
                logger.warning(
                    "voicemail: type='audio' but storage_key is NULL for "
                    "user_id=%s — falling back to default prompt",
                    user.id,
                )
        elif gtype == "text":
            text = (getattr(user, "voicemail_greeting_text", None) or "").strip()
            if text:
                response.say(
                    f"{text} Please leave a message after the beep. "
                    "Press the pound key when finished.",
                    voice="Polly.Joanna",
                )
                used_custom = True

    if not used_custom:
        name = (getattr(user, "full_name", None) if user else None) or ""
        if name.strip():
            first = name.strip().split()[0]
            response.say(
                f"{first} is unavailable. Please leave a message after the beep. "
                "Press the pound key when finished.",
                voice="Polly.Joanna",
            )
        else:
            response.say(
                "The person you're calling is unavailable. Please leave a message "
                "after the beep. Press the pound key when finished.",
                voice="Polly.Joanna",
            )

    response.append(
        Record(
            action="https://accountant.ocidm.io/api/communication/voice/voicemail-complete",
            recording_status_callback="https://accountant.ocidm.io/api/communication/voice/voicemail-status",
            recording_status_callback_method="POST",
            recording_status_callback_event="completed",
            max_length=120,
            play_beep=True,
            finish_on_key="#",
            transcribe=False,
            timeout=5,
        )
    )
    response.say("Sorry, we didn't hear anything. Goodbye.", voice="Polly.Joanna")
    response.hangup()
    return _xml_response(str(response))


async def _mark_kind_voicemail(db: AsyncSession, parent_call_sid: str) -> None:
    """Flip the call_logs row to kind='voicemail' once we know the call is
    routing to voicemail. Idempotent — safe to call multiple times for the
    same SID. Status stays 'pending' until the AssemblyAI task lands.
    """
    if not parent_call_sid:
        return
    result = await db.execute(
        select(CallLog).where(CallLog.twilio_call_sid == parent_call_sid)
    )
    call_log = result.scalar_one_or_none()
    if call_log is not None and call_log.kind != "voicemail":
        call_log.kind = "voicemail"
        call_log.voicemail_transcript_status = "pending"
        await db.commit()


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
    user_uuid: uuid.UUID | None = None
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
            user_uuid = None  # malformed UUID, fall through to global

    # Fall back to the global TWILIO_FROM_NUMBER if user has no assigned number
    if not caller_id:
        settings: Settings = request.app.state.settings
        caller_id = settings.twilio_from_number or None

    response = VoiceResponse()
    response.say(
        "This call may be recorded for quality and training purposes.",
        voice="Polly.Joanna",
    )
    dial_kwargs: dict = {
        "record": "record-from-answer-dual",
        "recording_status_callback": "https://accountant.ocidm.io/api/communication/voice/recording-status",
        "recording_status_callback_method": "POST",
        "recording_status_callback_event": "completed",
    }
    if caller_id:
        dial_kwargs["caller_id"] = caller_id
    dial = Dial(**dial_kwargs)
    # statusCallback belongs on the <Number>/<Client> noun, NOT on <Dial>.
    # Twilio silently ignores statusCallback attrs on <Dial> — only the nested
    # dialed-noun fires lifecycle webhooks.
    dial.number(
        to_number,
        status_callback="https://accountant.ocidm.io/api/communication/voice/call-status",
        status_callback_method="POST",
        status_callback_event="initiated ringing answered completed",
    )
    response.append(dial)

    # Create call_logs row synchronously so call-status + recording-status
    # webhooks have a row to update. Parent CallSid (from THIS TwiML POST)
    # is the canonical conversation ID. Guard on user_uuid + sid presence.
    parent_call_sid = form.get("CallSid", "")
    if parent_call_sid and user_uuid:
        call_log = CallLog(
            id=uuid.uuid4(),
            user_id=user_uuid,
            direction="outbound",
            from_number=caller_id or "",
            to_number=to_number,
            duration_seconds=0,
            status="initiated",
            twilio_call_sid=parent_call_sid,
        )
        db.add(call_log)
        try:
            await db.commit()
        except IntegrityError:
            # Duplicate twilio_call_sid — status webhook beat us here.
            # Rare but possible; benign.
            await db.rollback()
    else:
        if not parent_call_sid:
            logger.warning("voice_twiml: no CallSid in form; skipping call_log row creation")
        if not user_uuid:
            logger.warning("voice_twiml: no user resolved; skipping call_log row creation")

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
    caller_from = form.get("From", "")

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

    response.say(
        "This call may be recorded for quality and training purposes.",
        voice="Polly.Joanna",
    )
    # Dial the browser client; on timeout/no-answer, Twilio POSTs to action URL.
    # statusCallback belongs on the <Client> noun, NOT on <Dial> — Twilio
    # silently ignores it at the <Dial> level. recordingStatusCallback DOES
    # belong on <Dial> (the recording is a property of the bridge).
    dial = Dial(
        timeout=10,
        action="https://accountant.ocidm.io/api/communication/voice/incoming-fallback",
        record="record-from-answer-dual",
        recording_status_callback="https://accountant.ocidm.io/api/communication/voice/recording-status",
        recording_status_callback_method="POST",
        recording_status_callback_event="completed",
    )
    dial.client(
        str(phone.assigned_user_id),
        status_callback="https://accountant.ocidm.io/api/communication/voice/call-status",
        status_callback_method="POST",
        status_callback_event="initiated ringing answered completed",
    )
    response.append(dial)

    # Create call_logs row synchronously. Parent CallSid is the canonical
    # conversation ID. Guard on assigned_user + sid presence.
    parent_call_sid = form.get("CallSid", "")
    if parent_call_sid and phone.assigned_user_id is not None:
        call_log = CallLog(
            id=uuid.uuid4(),
            user_id=phone.assigned_user_id,
            direction="inbound",
            from_number=caller_from,
            to_number=phone.phone_number,
            duration_seconds=0,
            status="ringing",
            twilio_call_sid=parent_call_sid,
        )
        db.add(call_log)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    else:
        if not parent_call_sid:
            logger.warning("voice_incoming: no CallSid in form; skipping call_log row creation")
        if phone.assigned_user_id is None:
            logger.warning("voice_incoming: no assigned_user; skipping call_log row creation")

    return _xml_response(str(response))


@router.post("/voice/incoming-fallback")
async def voice_incoming_fallback(
    form: Annotated[dict, Depends(verified_twilio_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Fires after the browser-Dial finishes (success or timeout).

    If DialCallStatus == 'completed', the browser answered — return empty so
    Twilio hangs up cleanly. Otherwise, ring the assigned user's fallback_phone
    (cell). If no cell is set, OR if the cell dial fails too, the caller
    lands in voicemail via the cell <Dial>'s action= target.
    """
    from twilio.twiml.voice_response import VoiceResponse, Dial

    dial_status = form.get("DialCallStatus", "")
    called = form.get("Called", "") or form.get("To", "")  # 'Called' on incoming; 'To' on the fallback POST

    if dial_status == "completed":
        return _xml_response("<Response/>")

    # Look up phone + assigned user + fallback in one pass
    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == called)
    )
    phone = result.scalar_one_or_none()

    assigned_user: User | None = None
    fallback: str | None = None
    if phone is not None and phone.assigned_user_id is not None:
        user_result = await db.execute(
            select(User).where(User.id == phone.assigned_user_id)
        )
        assigned_user = user_result.scalar_one_or_none()
        if assigned_user is not None:
            fallback = getattr(assigned_user, "fallback_phone", None)

    parent_call_sid = form.get("CallSid", "")
    mode = (getattr(assigned_user, "voicemail_mode", None) if assigned_user
            else None) or "cell_then_voicemail"

    # cell_only: ring cell with NO voicemail action — if cell fails, hang up.
    if mode == "cell_only":
        if not fallback:
            response = VoiceResponse()
            response.say("Sorry, no one is available to take your call.")
            return _xml_response(str(response))
        response = VoiceResponse()
        dial = Dial(timeout=20, caller_id=called)  # no action= → silent hangup
        dial.number(
            fallback,
            status_callback="https://accountant.ocidm.io/api/communication/voice/call-status",
            status_callback_method="POST",
            status_callback_event="initiated ringing answered completed",
        )
        response.append(dial)
        return _xml_response(str(response))

    # voicemail_only: skip cell entirely, go straight to voicemail.
    if mode == "voicemail_only":
        await _mark_kind_voicemail(db, parent_call_sid)
        return _voicemail_response(assigned_user)

    # cell_then_voicemail (default):
    if not fallback:
        # No cell (no user, deleted phone, or user has no fallback_phone)
        # → voicemail directly. Caller still gets options.
        await _mark_kind_voicemail(db, parent_call_sid)
        return _voicemail_response(assigned_user)

    # Cell dial. On no-answer/fail, Twilio POSTs to action=/voice/voicemail.
    # statusCallback belongs on <Number>, NOT on <Dial> (Bug 1 lesson).
    response = VoiceResponse()
    dial = Dial(
        timeout=20,
        caller_id=called,
        action="https://accountant.ocidm.io/api/communication/voice/voicemail",
    )
    dial.number(
        fallback,
        status_callback="https://accountant.ocidm.io/api/communication/voice/call-status",
        status_callback_method="POST",
        status_callback_event="initiated ringing answered completed",
    )
    response.append(dial)
    return _xml_response(str(response))


@router.post("/voice/voicemail")
async def voice_voicemail(
    form: Annotated[dict, Depends(verified_twilio_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Fires when the cell-fallback <Dial> finishes without 'completed'.

    Plays voicemail prompt + opens <Record> for the caller. If the cell
    DID answer and the call completed naturally, short-circuit with an
    empty response — the call is already done, no voicemail needed.
    """
    dial_call_status = form.get("DialCallStatus", "")
    parent_call_sid = form.get("CallSid", "")

    if dial_call_status == "completed":
        logger.info(
            "voice/voicemail: short-circuit on completed call "
            "(ParentCallSid=%s, DialCallStatus=%s)",
            parent_call_sid,
            dial_call_status,
        )
        return _xml_response("<Response/>")

    called = form.get("Called", "") or form.get("To", "")

    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.phone_number == called)
    )
    phone = result.scalar_one_or_none()

    assigned_user: User | None = None
    if phone is not None and phone.assigned_user_id is not None:
        user_result = await db.execute(
            select(User).where(User.id == phone.assigned_user_id)
        )
        assigned_user = user_result.scalar_one_or_none()

    await _mark_kind_voicemail(db, parent_call_sid)
    return _voicemail_response(assigned_user)


@router.post("/voice/voicemail-complete")
async def voice_voicemail_complete(
    _form: Annotated[dict, Depends(verified_twilio_form)],
) -> Response:
    """Fires when <Record> ends (caller hangup, # press, or maxLength reached).

    Close the call cleanly. The actual recording-row update happens in
    /voice/voicemail-status when Twilio finishes processing the audio.

    _form is required for the signature-verification Depends; we don't read
    the body here (the recording metadata arrives via voicemail-status).
    """
    from twilio.twiml.voice_response import VoiceResponse

    response = VoiceResponse()
    response.say("Thank you. Goodbye.", voice="Polly.Joanna")
    response.hangup()
    return _xml_response(str(response))


@router.post("/voice/voicemail-status")
async def voice_voicemail_status(
    form: Annotated[dict, Depends(verified_twilio_form)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> Response:
    """Fires when the voicemail recording is processed + durable.

    Persists recording metadata onto the call_logs row, then schedules
    fire-and-forget AssemblyAI transcription via BackgroundTasks.
    """
    call_sid = form.get("CallSid", "")
    recording_sid = form.get("RecordingSid", "")
    recording_url = form.get("RecordingUrl", "")
    recording_duration = form.get("RecordingDuration", "0")

    if not call_sid or not recording_sid:
        return _xml_response("<Response/>")

    result = await db.execute(
        select(CallLog).where(CallLog.twilio_call_sid == call_sid)
    )
    call_log = result.scalar_one_or_none()
    if call_log is None:
        logger.warning(
            "voice/voicemail-status: no call_logs row for CallSid=%s "
            "(unmatched parent — likely race condition with incoming)",
            call_sid,
        )
        return _xml_response("<Response/>")

    call_log.kind = "voicemail"
    call_log.recording_sid = recording_sid
    call_log.recording_url = recording_url
    try:
        call_log.recording_duration_seconds = int(recording_duration)
    except (ValueError, TypeError):
        call_log.recording_duration_seconds = 0
    call_log.recording_status = "completed"

    # Only transcribe if there's actual content. 0-duration recordings
    # would waste an AssemblyAI API call.
    if call_log.recording_duration_seconds and call_log.recording_duration_seconds > 0:
        call_log.voicemail_transcript_status = "pending"
        call_log_id = call_log.id
        await db.commit()
        settings: Settings = request.app.state.settings
        from app.communication.voicemail import transcribe_voicemail_task
        background_tasks.add_task(
            transcribe_voicemail_task,
            call_log_id=call_log_id,
            recording_sid=recording_sid,
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            session_factory=request.app.state.session_factory,
        )
    else:
        call_log_id = call_log.id
        await db.commit()

    # Trigger the 'voicemail' automation flow regardless of transcription
    # outcome. If user has no flow for this trigger, the engine skips.
    # Use BackgroundTasks (NOT asyncio.create_task) — the latter only holds
    # a weak reference and the coroutine can be GC'd before it runs.
    if call_log.automation_flow_triggered_at is None and call_log.user_id is not None:
        from app.communication.automation_engine import trigger_flow_for_call
        background_tasks.add_task(
            trigger_flow_for_call,
            call_log_id=call_log_id,
            trigger_type="voicemail",
            session_factory=request.app.state.session_factory,
        )

    return _xml_response("<Response/>")


@router.get("/voicemail-greeting/{user_id}.mp3")
async def stream_voicemail_greeting(
    user_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Stream a user's voicemail greeting audio. PUBLIC — no auth.

    Twilio's <Play> verb fetches this at call time. Greetings are inherently
    public (anyone who calls the user's Twilio number hears them), so adding
    auth here would just block Twilio. 404 if user has no audio greeting or
    if R2 read fails.

    Cache-Control: no-store on ALL responses. Cloudflare in front of us will
    cache 404s and stale 200s by default; that would break greeting updates
    AND prevent any audio from playing if Twilio's first probe (before upload)
    cached a 404. Twilio's call volume is too low for CDN caching to matter.
    """
    no_cache = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.voicemail_greeting_type != "audio":
        return Response(
            content='{"detail":"No audio greeting"}',
            status_code=404,
            media_type="application/json",
            headers=no_cache,
        )
    if not user.voicemail_greeting_storage_key:
        return Response(
            content='{"detail":"No audio greeting"}',
            status_code=404,
            media_type="application/json",
            headers=no_cache,
        )

    from app.communication.voicemail_storage import read_greeting
    settings: Settings = request.app.state.settings
    mp3_bytes = await read_greeting(settings, user.voicemail_greeting_storage_key)
    if mp3_bytes is None:
        return Response(
            content='{"detail":"Greeting unavailable"}',
            status_code=404,
            media_type="application/json",
            headers=no_cache,
        )

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers=no_cache,
    )


@router.post("/voice/call-status")
async def voice_call_status(
    form: Annotated[dict, Depends(verified_twilio_form)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> Response:
    """Twilio fires this on Dial-leg lifecycle events.

    The status callback runs against the CHILD call leg (the one created by
    <Dial>), but we key call_logs by the PARENT/conversation SID — recording
    is on the parent. Twilio passes ParentCallSid for correlation.

    Additionally: when the user's voicemail_mode is 'cell_only' and the call
    ends missed (no-answer/busy/failed), trigger their 'missed_call' automation
    flow. Voicemail-mode users get their flow fired from voicemail-status
    instead (after the transcript lands).
    """
    parent_call_sid = form.get("ParentCallSid", "")
    if not parent_call_sid:
        # Some lifecycle events lack ParentCallSid; nothing to correlate.
        return _xml_response("<Response/>")

    call_status = form.get("CallStatus", "")
    call_duration = form.get("CallDuration", "0")

    result = await db.execute(
        select(CallLog).where(CallLog.twilio_call_sid == parent_call_sid)
    )
    call_log = result.scalar_one_or_none()
    if call_log is None:
        logger.warning(
            "voice/call-status: no call_logs row for ParentCallSid=%s (race or unseen call)",
            parent_call_sid,
        )
        return _xml_response("<Response/>")

    if call_status == "completed":
        call_log.status = "completed"
        try:
            call_log.duration_seconds = int(call_duration)
        except (ValueError, TypeError):
            pass
    elif call_status in ("ringing", "in-progress", "busy", "failed", "no-answer", "canceled"):
        call_log.status = call_status

    await db.commit()

    # Trigger missed_call automation for cell_only users.
    # Use BackgroundTasks (not asyncio.create_task) for the same weak-ref
    # reason — see voice_voicemail_status comment above.
    if (
        call_status in ("no-answer", "busy", "failed")
        and call_log.kind != "voicemail"
        and call_log.user_id is not None
        and call_log.automation_flow_triggered_at is None
    ):
        user_row = await db.execute(
            select(User).where(User.id == call_log.user_id)
        )
        user = user_row.scalar_one_or_none()
        if user is not None and user.voicemail_mode == "cell_only":
            from app.communication.automation_engine import trigger_flow_for_call
            background_tasks.add_task(
                trigger_flow_for_call,
                call_log_id=call_log.id,
                trigger_type="missed_call",
                session_factory=request.app.state.session_factory,
            )

    return _xml_response("<Response/>")


@router.post("/voice/recording-status")
async def voice_recording_status(
    form: Annotated[dict, Depends(verified_twilio_form)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Twilio fires this when recording finishes processing.

    CallSid here IS the parent SID — recordings are on the parent leg.
    """
    call_sid = form.get("CallSid", "")
    recording_sid = form.get("RecordingSid", "")
    recording_url = form.get("RecordingUrl", "")
    recording_duration = form.get("RecordingDuration", "0")
    recording_status = form.get("RecordingStatus", "")

    if not call_sid or not recording_sid:
        return _xml_response("<Response/>")

    result = await db.execute(
        select(CallLog).where(CallLog.twilio_call_sid == call_sid)
    )
    call_log = result.scalar_one_or_none()
    if call_log is None:
        logger.warning(
            "voice/recording-status: no call_logs row for CallSid=%s (race or unseen call)",
            call_sid,
        )
        return _xml_response("<Response/>")

    call_log.recording_sid = recording_sid
    call_log.recording_url = recording_url
    try:
        call_log.recording_duration_seconds = int(recording_duration)
    except (ValueError, TypeError):
        pass
    call_log.recording_status = recording_status or "completed"
    await db.commit()
    return _xml_response("<Response/>")


@router.get("/calls/{call_id}/recording")
async def stream_call_recording(
    call_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_token)],
) -> StreamingResponse:
    """Proxy a Twilio recording through our auth gate.

    Twilio recording URLs require Account-SID Basic Auth — we can't expose
    them directly to the browser. This streams audio/mpeg bytes from Twilio
    with our credentials, gated by user-owns-the-call (or admin).

    Uses get_current_user_or_token so the native <audio> element can pass
    the JWT via ?token= query string — it has no API for Authorization
    headers. Same convention as document preview / meeting media / Gmail
    attachments. Token leaks via uvicorn access logs are acceptable for
    this internal admin platform; revisit when going multi-tenant.
    """
    settings: Settings = request.app.state.settings

    result = await db.execute(select(CallLog).where(CallLog.id == call_id))
    call_log = result.scalar_one_or_none()
    if call_log is None:
        raise HTTPException(status_code=404, detail="Call not found")

    if (
        call_log.user_id is not None
        and call_log.user_id != current_user.id
        and current_user.role != Role.ADMIN
    ):
        raise HTTPException(status_code=403, detail="Not authorized for this recording")

    if not call_log.recording_sid:
        raise HTTPException(status_code=404, detail="No recording available for this call")

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise HTTPException(status_code=500, detail="Twilio is not configured")

    import httpx

    twilio_url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
        f"/Recordings/{call_log.recording_sid}.mp3"
    )
    client = httpx.AsyncClient(timeout=60.0)

    async def stream_bytes():
        try:
            async with client.stream(
                "GET",
                twilio_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            ) as upstream:
                if upstream.status_code >= 400:
                    return
                async for chunk in upstream.aiter_bytes(chunk_size=8192):
                    yield chunk
        finally:
            await client.aclose()

    return StreamingResponse(stream_bytes(), media_type="audio/mpeg")


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

    # Auto-configure webhooks. Wrapped in try/except — if webhook config
    # fails, the number is still purchased (don't lose it). UI surfaces
    # the "Not configured" state and offers a Sync Webhooks button.
    from datetime import datetime, timezone
    webhooks_configured_at = None
    webhook_config_error: str | None = None
    try:
        await service.configure_twilio_webhooks(settings, purchased.sid)
        webhooks_configured_at = datetime.now(timezone.utc)
    except Exception as e:
        webhook_config_error = str(e)[:200]
        logger.warning(
            "purchase: webhook auto-config failed for sid=%s — number kept, "
            "Sync Webhooks button will retry. error=%s",
            purchased.sid, webhook_config_error,
        )

    phone = TwilioPhoneNumber(
        id=uuid.uuid4(),
        phone_number=purchased.phone_number,
        friendly_name=purchased.friendly_name or phone_number,
        capabilities_json=capabilities_data,
        webhooks_configured_at=webhooks_configured_at,
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
            "webhooks_configured_at": (
                webhooks_configured_at.isoformat() if webhooks_configured_at else None
            ),
            "webhook_config_error": webhook_config_error,
        }
    }


@router.post("/phone-numbers/{phone_id}/sync-webhooks")
async def sync_phone_number_webhooks(
    phone_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Push our webhook URLs onto an existing Twilio number.

    Used for numbers bought outside the platform (or for whom auto-config
    on purchase failed). Idempotent — safe to re-run.
    """
    from datetime import datetime, timezone

    settings: Settings = request.app.state.settings

    result = await db.execute(
        select(TwilioPhoneNumber).where(TwilioPhoneNumber.id == phone_id)
    )
    phone = result.scalar_one_or_none()
    if phone is None:
        raise HTTPException(status_code=404, detail="Phone number not found")

    # Extract the Twilio SID from capabilities_json. We store it there at
    # purchase time. For numbers added via the legacy admin form (pre-API
    # integration), capabilities_json may not have a sid — those rows can't
    # be synced and need to be re-added.
    twilio_sid: str | None = None
    if phone.capabilities_json:
        try:
            blob = json.loads(phone.capabilities_json)
            twilio_sid = blob.get("sid")
        except (ValueError, TypeError):
            pass
    if not twilio_sid:
        raise HTTPException(
            status_code=400,
            detail=(
                "No Twilio SID on record for this number. Add it via Buy "
                "Number, or update the row's capabilities_json manually."
            ),
        )

    try:
        urls = await service.configure_twilio_webhooks(settings, twilio_sid)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    phone.webhooks_configured_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(phone)

    return {
        "data": {
            "id": str(phone.id),
            "webhooks_configured_at": phone.webhooks_configured_at.isoformat(),
            "webhook_urls": urls,
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
