"""Brain API router — chat, conversations, recordings, knowledge base, alerts, audit."""

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db
from app.brain import (
    chat_service,
    transcription_service,
    knowledge_service,
    proactive_service,
)
from app.brain.models import (
    BrainAuditLog,
    AuditActionType,
    TranscriptionStatus,
)
from app.brain.schemas import (
    ChatRequest,
    ChatMessageResponse,
    ConversationResponse,
    ConversationDetailResponse,
    KnowledgeAddRequest,
    KnowledgeItemResponse,
    AlertResponse,
    AuditLogResponse,
    OnboardingAnswerRequest,
    BrainSearchRequest,
    BrainSearchResult,
)
from app.brain.retrieval_service import search_brain

router = APIRouter()


# ── Chat ──────────────────────────────────────────────────────────────


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Stream a chat response via SSE."""
    return StreamingResponse(
        chat_service.chat_stream(
            db=db,
            user_id=user.id,
            message=body.message,
            conversation_id=body.conversation_id,
            page_context=body.page_context or "General",
            file_ids=body.file_ids,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/upload")
async def upload_chat_file(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
):
    """Upload a file to attach to a brain chat message."""
    import os
    from app.config import Settings
    from app.core.exceptions import ValidationError as AppValidationError

    settings = Settings()

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise AppValidationError("File too large. Maximum size is 10MB.")

    file_id = uuid.uuid4()
    upload_dir = os.path.join(settings.storage_path, "brain_uploads")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "file")[1]
    storage_path = f"brain_uploads/{file_id}{ext}"
    full_path = os.path.join(settings.storage_path, storage_path)

    with open(full_path, "wb") as f:
        f.write(contents)

    conv = await chat_service.get_or_create_conversation(db, user.id, conversation_id)

    from app.brain.models import BrainChatFile
    chat_file = BrainChatFile(
        id=file_id,
        conversation_id=conv.id,
        user_id=user.id,
        original_filename=file.filename or "file",
        storage_path=storage_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(contents),
    )
    db.add(chat_file)
    await db.commit()
    await db.refresh(chat_file)

    return {
        "data": {
            "id": str(chat_file.id),
            "conversation_id": str(conv.id),
            "original_filename": chat_file.original_filename,
            "mime_type": chat_file.mime_type,
            "file_size": chat_file.file_size,
        }
    }


# ── Conversations ─────────────────────────────────────────────────────


@router.get("/conversations")
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
):
    convs = await chat_service.list_conversations(db, user.id, limit)
    return {
        "data": [
            ConversationResponse(
                id=str(c.id),
                title=c.title,
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else "",
                message_count=len(c.messages) if c.messages else 0,
            ).model_dump()
            for c in convs
        ]
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    conv = await chat_service.get_conversation(db, user.id, conversation_id)
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(404, "Conversation not found")

    messages = [
        ChatMessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            tools_used=json.loads(m.tools_used_json) if m.tools_used_json else None,
            sources=json.loads(m.sources_cited_json) if m.sources_cited_json else None,
            created_at=m.created_at.isoformat() if m.created_at else "",
        ).model_dump()
        for m in (conv.messages or [])
    ]

    return {
        "data": ConversationDetailResponse(
            id=str(conv.id),
            title=conv.title,
            created_at=conv.created_at.isoformat() if conv.created_at else "",
            updated_at=conv.updated_at.isoformat() if conv.updated_at else "",
            messages=messages,
        ).model_dump()
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    deleted = await chat_service.delete_conversation(db, user.id, conversation_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(404, "Conversation not found")
    return {"data": {"deleted": True}}


# ── Knowledge Base ────────────────────────────────────────────────────


@router.post("/knowledge")
async def add_knowledge(
    body: KnowledgeAddRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await knowledge_service.add_knowledge(
        db, user.id, body.content, body.title, body.category,
    )
    return {"data": result}


@router.get("/knowledge")
async def list_knowledge(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = await knowledge_service.list_knowledge(db, user.id, category, page, page_size)
    return {"data": result}


@router.delete("/knowledge/{source_id}")
async def delete_knowledge(
    source_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    deleted = await knowledge_service.delete_knowledge(db, user.id, source_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(404, "Knowledge item not found")
    return {"data": {"deleted": True}}


@router.get("/knowledge/onboarding")
async def get_onboarding_questions(
    _: Annotated[User, Depends(get_current_user)],
):
    return {"data": knowledge_service.get_onboarding_questions()}


@router.post("/knowledge/onboarding")
async def submit_onboarding(
    body: OnboardingAnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    count = await knowledge_service.process_onboarding_answers(db, user.id, body.answers)
    return {"data": {"stored": count}}


# ── Search ────────────────────────────────────────────────────────────


@router.post("/search")
async def search(
    body: BrainSearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    source_types = [body.source_type] if body.source_type else body.source_types
    results = await search_brain(
        db, user.id, body.query, limit=body.limit or 10, source_types=source_types,
    )
    return {
        "data": [
            BrainSearchResult(
                content=r.content[:500],
                source_type=r.source_type,
                source_id=r.source_id,
                relevance_score=round(r.relevance_score, 3),
            ).model_dump()
            for r in results
        ]
    }


# ── Transcription ─────────────────────────────────────────────────────


@router.post("/transcribe/meeting/{meeting_id}")
async def transcribe_meeting(
    meeting_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    language: str = Form("en"),
):
    audio_bytes = await file.read()
    transcript = await transcription_service.process_meeting_recording(
        db, user.id, meeting_id, audio_bytes, language,
    )
    return {
        "data": {
            "id": str(transcript.id),
            "text": transcript.full_text[:500],
            "duration_seconds": transcript.duration_seconds,
            "action_items": json.loads(transcript.action_items_json) if transcript.action_items_json else [],
        }
    }


@router.post("/transcribe/call")
async def transcribe_call(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    call_sid: str = Form(...),
    contact_id: uuid.UUID | None = Form(None),
    language: str = Form("en"),
):
    audio_bytes = await file.read()
    transcript = await transcription_service.process_call_recording(
        db, user.id, call_sid, contact_id, audio_bytes, language,
    )
    return {
        "data": {
            "id": str(transcript.id),
            "text": transcript.full_text[:500],
            "duration_seconds": transcript.duration_seconds,
            "action_items": json.loads(transcript.action_items_json) if transcript.action_items_json else [],
        }
    }


@router.post("/transcribe/import")
async def import_transcript(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    text: str = Form(...),
    source_type: str = Form("meeting"),
    meeting_id: uuid.UUID | None = Form(None),
    call_sid: str | None = Form(None),
    contact_id: uuid.UUID | None = Form(None),
):
    transcript = await transcription_service.import_external_transcript(
        db, user.id, text, source_type, meeting_id, call_sid, contact_id,
    )
    return {
        "data": {
            "id": str(transcript.id),
            "text": transcript.full_text[:500],
            "action_items": json.loads(transcript.action_items_json) if transcript.action_items_json else [],
        }
    }


@router.get("/transcription-queue")
async def list_transcription_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
):
    ts = TranscriptionStatus(status) if status else None
    items = await transcription_service.list_queue_items(db, user.id, ts)
    return {
        "data": [
            {
                "id": str(item.id),
                "source_type": item.source_type,
                "source_id": item.source_id,
                "status": item.status.value,
                "attempts": item.attempts,
                "error_message": item.error_message,
                "created_at": item.created_at.isoformat() if item.created_at else "",
            }
            for item in items
        ]
    }


# ── Alerts ────────────────────────────────────────────────────────────


@router.get("/alerts")
async def list_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
):
    alerts = await proactive_service.list_alerts(db, user.id, unread_only, limit)
    return {
        "data": [
            AlertResponse(
                id=str(a.id),
                alert_type=a.alert_type.value,
                title=a.title,
                message=a.message,
                is_read=a.is_read,
                data=json.loads(a.data_json) if a.data_json else None,
                created_at=a.created_at.isoformat() if a.created_at else "",
            ).model_dump()
            for a in alerts
        ]
    }


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ok = await proactive_service.mark_alert_read(db, alert_id, user.id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(404, "Alert not found")
    return {"data": {"read": True}}


@router.post("/alerts/read-all")
async def mark_all_alerts_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    count = await proactive_service.mark_all_alerts_read(db, user.id)
    return {"data": {"marked_read": count}}


@router.get("/briefing")
async def get_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    briefing = await proactive_service.get_daily_briefing(db, user.id)
    return {"data": briefing}


@router.post("/briefing/generate")
async def generate_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    alerts = await proactive_service.generate_daily_briefing(db, user.id)
    return {"data": {"generated": len(alerts)}}


# ── Audit ─────────────────────────────────────────────────────────────


@router.get("/audit")
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
):
    from sqlalchemy import select, desc
    stmt = (
        select(BrainAuditLog)
        .where(BrainAuditLog.user_id == user.id)
        .order_by(desc(BrainAuditLog.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    return {
        "data": [
            AuditLogResponse(
                id=str(log.id),
                action_type=log.action_type.value,
                ai_input=log.ai_input[:200] if log.ai_input else None,
                ai_output=log.ai_output[:200] if log.ai_output else None,
                human_decision=log.human_decision,
                created_at=log.created_at.isoformat() if log.created_at else "",
            ).model_dump()
            for log in logs
        ]
    }


# ── Discovery ─────────────────────────────────────────────────────────


@router.get("/discovery/questions")
async def get_discovery_questions(
    _: Annotated[User, Depends(get_current_user)],
):
    """Get all 28 discovery questions organized by section."""
    from app.brain.discovery_service import get_discovery_sections
    return {"data": get_discovery_sections()}


@router.post("/discovery/submit")
async def submit_discovery(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Submit discovery answers. Each answer is embedded into the brain."""
    from app.brain.discovery_service import save_discovery_answers
    answers = body.get("answers", [])
    result = await save_discovery_answers(db, user.id, answers)
    return {"data": result}
