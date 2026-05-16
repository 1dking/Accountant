"""R2-backed storage for user voicemail greetings.

Standalone helper that bypasses the global storage_type switch — voicemail
greetings always go to R2 regardless of where documents live. Twilio <Play>
can't fetch R2 directly (private bucket, SigV4 required), so we expose the
audio via a backend proxy endpoint that streams these bytes back.

Audio always stored as .mp3 (uniform downstream). Non-mp3 uploads are
transcoded via ffmpeg. Non-audio inputs (text-file-renamed-to-mp3 etc.)
fail the ffmpeg pipeline and are rejected — that IS our content gate.
"""

import asyncio
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
}

MAX_GREETING_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB hard cap


def _build_client(settings):
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _greeting_key(user_id: uuid.UUID) -> str:
    return f"voicemail-greetings/{user_id}/{uuid.uuid4().hex}.mp3"


async def transcode_to_mp3(audio_bytes: bytes, source_mime: str) -> bytes:
    """Transcode supported audio MIME to 128kbps mp3 via ffmpeg.

    Skipped when source is already audio/mpeg (passthrough). Raises
    ValueError on ffmpeg non-zero exit — that fires when input isn't real
    audio (e.g., a text file renamed .mp3), which IS the content gate.
    """
    if source_mime == "audio/mpeg":
        return audio_bytes

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i", "pipe:0",
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-f", "mp3",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    mp3_bytes, stderr = await proc.communicate(input=audio_bytes)
    if proc.returncode != 0:
        err_tail = (stderr or b"").decode(errors="replace")[-300:]
        raise ValueError(f"ffmpeg transcode failed: {err_tail}")
    return mp3_bytes


async def save_greeting(settings, user_id: uuid.UUID, mp3_bytes: bytes) -> str:
    """Upload mp3 bytes to R2 at voicemail-greetings/{user_id}/{uuid}.mp3.
    Returns the R2 storage key."""
    key = _greeting_key(user_id)
    client = _build_client(settings)
    await asyncio.to_thread(
        client.put_object,
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=mp3_bytes,
        ContentType="audio/mpeg",
    )
    logger.info("voicemail_storage.save user_id=%s key=%s bytes=%d",
                user_id, key, len(mp3_bytes))
    return key


async def delete_greeting(settings, storage_key: str) -> None:
    """Delete an R2 object. Never raises — orphan storage is preferable
    to blocking a user's UI on R2 hiccups."""
    if not storage_key:
        return
    try:
        client = _build_client(settings)
        await asyncio.to_thread(
            client.delete_object,
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
        )
        logger.info("voicemail_storage.delete key=%s", storage_key)
    except Exception as e:
        logger.warning(
            "voicemail_storage.delete_failed key=%s error=%s",
            storage_key, str(e)[:200],
        )


async def read_greeting(settings, storage_key: str) -> Optional[bytes]:
    """Read greeting bytes from R2. Returns None on any failure (404,
    network, etc.) — caller translates that to HTTP 404."""
    if not storage_key:
        return None
    try:
        client = _build_client(settings)
        resp = await asyncio.to_thread(
            client.get_object,
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
        )
        return await asyncio.to_thread(resp["Body"].read)
    except Exception as e:
        logger.warning(
            "voicemail_storage.read_failed key=%s error=%s",
            storage_key, str(e)[:200],
        )
        return None
