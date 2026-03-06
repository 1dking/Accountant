"""Transcription service — Whisper API + post-processing pipeline."""

import json
import logging
import re
import uuid
from datetime import datetime

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import (
    MeetingTranscript,
    CallTranscript,
    TranscriptionQueueItem,
    TranscriptionStatus,
)
from app.brain.embedding_service import embed_and_store, EmbeddingSourceType
from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

MAX_ATTEMPTS = 3


async def transcribe_audio(file_bytes: bytes, language: str = "en") -> dict:
    """Transcribe audio using OpenAI Whisper API.

    Returns: {"text": str, "segments": list[dict], "language": str, "duration": float}
    """
    if not settings.openai_api_key:
        raise ValueError("No OpenAI API key configured for transcription")

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": ("audio.webm", file_bytes, "audio/webm")},
            data={
                "model": "whisper-1",
                "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def transcribe_with_assemblyai(file_bytes: bytes) -> dict:
    """Fallback transcription using AssemblyAI.

    Returns: {"text": str, "segments": list[dict], "language": str, "duration": float}
    """
    if not settings.assemblyai_api_key:
        raise ValueError("No AssemblyAI API key configured")

    headers = {"authorization": settings.assemblyai_api_key}

    async with httpx.AsyncClient(timeout=300) as client:
        # Upload
        upload_resp = await client.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            content=file_bytes,
        )
        upload_resp.raise_for_status()
        upload_url = upload_resp.json()["upload_url"]

        # Transcribe
        transcript_resp = await client.post(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            json={
                "audio_url": upload_url,
                "speaker_labels": True,
                "language_detection": True,
            },
        )
        transcript_resp.raise_for_status()
        transcript_id = transcript_resp.json()["id"]

        # Poll for completion
        import asyncio
        for _ in range(120):  # 10 minutes max
            poll_resp = await client.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers,
            )
            poll_resp.raise_for_status()
            data = poll_resp.json()
            if data["status"] == "completed":
                segments = []
                for utt in data.get("utterances", []):
                    segments.append({
                        "start": utt["start"] / 1000,
                        "end": utt["end"] / 1000,
                        "text": utt["text"],
                        "speaker": utt.get("speaker", "Unknown"),
                    })
                return {
                    "text": data["text"],
                    "segments": segments,
                    "language": data.get("language_code", "en"),
                    "duration": data.get("audio_duration", 0),
                }
            if data["status"] == "error":
                raise RuntimeError(f"AssemblyAI error: {data.get('error', 'Unknown')}")
            await asyncio.sleep(5)

        raise TimeoutError("AssemblyAI transcription timed out")


def _extract_speakers(segments: list[dict]) -> list[dict]:
    """Extract unique speakers from transcript segments."""
    speakers = {}
    for seg in segments:
        speaker = seg.get("speaker", "Speaker")
        if speaker not in speakers:
            speakers[speaker] = {
                "name": speaker,
                "segments_count": 0,
                "total_duration": 0,
            }
        speakers[speaker]["segments_count"] += 1
        duration = (seg.get("end", 0) or 0) - (seg.get("start", 0) or 0)
        speakers[speaker]["total_duration"] += duration
    return list(speakers.values())


def _extract_action_items(text: str) -> list[str]:
    """Extract action items from transcript text using patterns."""
    patterns = [
        r"(?:I'll|I will|we'll|we will|let me|let's)\s+(.+?)(?:\.|$)",
        r"(?:action item|todo|to-do|follow up|follow-up)[:\s]+(.+?)(?:\.|$)",
        r"(?:need to|have to|should|must)\s+(.+?)(?:\.|$)",
        r"(?:can you|could you|would you)\s+(.+?)(?:\.|$)",
    ]
    items = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip()
            if 10 < len(cleaned) < 200:
                items.append(cleaned)
    # Deduplicate
    seen = set()
    unique = []
    for item in items:
        key = item.lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:20]  # Cap at 20


def _extract_financial_commitments(text: str) -> list[dict]:
    """Extract financial mentions from transcript text."""
    patterns = [
        r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:per|a|\/)\s*(?:month|year|hour|week|day))?',
        r'(?:budget|cost|price|fee|rate|salary|payment|invoice)\s+(?:of|is|was|at|around|about)?\s*\$?[\d,]+(?:\.\d{2})?',
        r'[\d,]+(?:\.\d{2})?\s*(?:dollars|usd|USD)',
    ]
    commitments = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            commitments.append({
                "amount_text": match.group(),
                "context": context,
            })
    return commitments[:15]


async def process_meeting_recording(
    db: AsyncSession,
    user_id: uuid.UUID,
    meeting_id: uuid.UUID,
    audio_bytes: bytes,
    language: str = "en",
) -> MeetingTranscript:
    """Full post-meeting processing pipeline.

    1. Transcribe audio
    2. Extract speakers, action items, financial commitments
    3. Store transcript
    4. Embed for search
    """
    # Transcribe
    try:
        result = await transcribe_audio(audio_bytes, language)
    except Exception:
        logger.warning("Whisper failed, trying AssemblyAI fallback")
        result = await transcribe_with_assemblyai(audio_bytes)

    segments = result.get("segments", [])
    speakers = _extract_speakers(segments)
    action_items = _extract_action_items(result["text"])
    financial = _extract_financial_commitments(result["text"])

    transcript = MeetingTranscript(
        id=uuid.uuid4(),
        meeting_id=meeting_id,
        user_id=user_id,
        full_text=result["text"],
        speakers_json=json.dumps(speakers),
        summary=result["text"][:500],
        action_items_json=json.dumps(action_items),
        financial_commitments_json=json.dumps(financial),
        language=result.get("language", language),
        duration_seconds=int(result.get("duration", 0)),
    )
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    # Embed for search
    try:
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=result["text"],
            source_type=EmbeddingSourceType.MEETING_TRANSCRIPT,
            source_id=str(transcript.id),
        )
    except Exception as e:
        logger.error(f"Failed to embed meeting transcript: {e}")

    return transcript


async def process_call_recording(
    db: AsyncSession,
    user_id: uuid.UUID,
    call_sid: str,
    contact_id: uuid.UUID | None,
    audio_bytes: bytes,
    language: str = "en",
) -> CallTranscript:
    """Full post-call processing pipeline."""
    try:
        result = await transcribe_audio(audio_bytes, language)
    except Exception:
        logger.warning("Whisper failed, trying AssemblyAI fallback")
        result = await transcribe_with_assemblyai(audio_bytes)

    segments = result.get("segments", [])
    speakers = _extract_speakers(segments)
    action_items = _extract_action_items(result["text"])
    financial = _extract_financial_commitments(result["text"])

    transcript = CallTranscript(
        id=uuid.uuid4(),
        call_sid=call_sid,
        user_id=user_id,
        contact_id=contact_id,
        full_text=result["text"],
        speakers_json=json.dumps(speakers),
        summary=result["text"][:500],
        action_items_json=json.dumps(action_items),
        financial_commitments_json=json.dumps(financial),
        language=result.get("language", language),
        duration_seconds=int(result.get("duration", 0)),
    )
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    # Embed for search
    try:
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=result["text"],
            source_type=EmbeddingSourceType.CALL_TRANSCRIPT,
            source_id=str(transcript.id),
            contact_id=contact_id,
        )
    except Exception as e:
        logger.error(f"Failed to embed call transcript: {e}")

    return transcript


async def import_external_transcript(
    db: AsyncSession,
    user_id: uuid.UUID,
    text: str,
    source_type: str = "meeting",
    meeting_id: uuid.UUID | None = None,
    call_sid: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> MeetingTranscript | CallTranscript:
    """Import an external transcript (pasted text or uploaded file)."""
    action_items = _extract_action_items(text)
    financial = _extract_financial_commitments(text)

    if source_type == "call" and call_sid:
        transcript = CallTranscript(
            id=uuid.uuid4(),
            call_sid=call_sid,
            user_id=user_id,
            contact_id=contact_id,
            full_text=text,
            summary=text[:500],
            action_items_json=json.dumps(action_items),
            financial_commitments_json=json.dumps(financial),
        )
        embed_source = EmbeddingSourceType.CALL_TRANSCRIPT
    else:
        transcript = MeetingTranscript(
            id=uuid.uuid4(),
            meeting_id=meeting_id or uuid.uuid4(),
            user_id=user_id,
            full_text=text,
            summary=text[:500],
            action_items_json=json.dumps(action_items),
            financial_commitments_json=json.dumps(financial),
        )
        embed_source = EmbeddingSourceType.MEETING_TRANSCRIPT

    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    try:
        await embed_and_store(
            db=db,
            user_id=user_id,
            content=text,
            source_type=embed_source,
            source_id=str(transcript.id),
            contact_id=contact_id,
        )
    except Exception as e:
        logger.error(f"Failed to embed imported transcript: {e}")

    return transcript


# ── Queue management ──────────────────────────────────────────────────

async def enqueue_transcription(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_type: str,
    source_id: str,
    recording_path: str,
) -> TranscriptionQueueItem:
    """Add a recording to the transcription queue."""
    item = TranscriptionQueueItem(
        id=uuid.uuid4(),
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        recording_path=recording_path,
        status=TranscriptionStatus.PENDING,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def process_queue(db: AsyncSession) -> int:
    """Process pending items in the transcription queue. Returns count processed."""
    stmt = select(TranscriptionQueueItem).where(
        and_(
            TranscriptionQueueItem.status == TranscriptionStatus.PENDING,
            TranscriptionQueueItem.attempts < MAX_ATTEMPTS,
        )
    ).limit(10)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    processed = 0
    for item in items:
        item.status = TranscriptionStatus.PROCESSING
        item.attempts += 1
        await db.commit()

        try:
            # Read audio file
            import aiofiles
            async with aiofiles.open(item.recording_path, "rb") as f:
                audio_bytes = await f.read()

            if item.source_type == "meeting":
                await process_meeting_recording(
                    db, item.user_id, uuid.UUID(item.source_id), audio_bytes,
                )
            elif item.source_type == "call":
                await process_call_recording(
                    db, item.user_id, item.source_id, None, audio_bytes,
                )

            item.status = TranscriptionStatus.COMPLETED
            item.completed_at = datetime.utcnow()
            processed += 1
        except Exception as e:
            logger.error(f"Transcription queue error for {item.id}: {e}")
            item.error_message = str(e)[:500]
            if item.attempts >= MAX_ATTEMPTS:
                item.status = TranscriptionStatus.DEAD_LETTER
            else:
                item.status = TranscriptionStatus.PENDING

        await db.commit()

    return processed


async def list_queue_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: TranscriptionStatus | None = None,
) -> list[TranscriptionQueueItem]:
    """List transcription queue items for a user."""
    stmt = select(TranscriptionQueueItem).where(
        TranscriptionQueueItem.user_id == user_id
    )
    if status:
        stmt = stmt.where(TranscriptionQueueItem.status == status)
    stmt = stmt.order_by(TranscriptionQueueItem.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    return list(result.scalars().all())
