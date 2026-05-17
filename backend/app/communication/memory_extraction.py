"""AI memory extraction for contact intelligence.

Given a chunk of conversation text (voicemail transcript, SMS thread,
manual paste), Claude Haiku 4.5 returns 4 structured fields capturing
what was said and what to bring up next time. Fast + cheap by design —
this runs on every voicemail and arbitrary contact interactions.
"""

import json
import logging
import re

import anthropic

from app.config import Settings

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600

SYSTEM_PROMPT = """You extract structured memory from a conversation snippet. \
Return JSON ONLY (no markdown fences, no prose), matching this schema:

{
  "summary": "1-2 sentence overview of what was discussed",
  "commitments": "What was agreed or promised (or 'none')",
  "cares_about": "What the caller cares about, their interests or concerns (or 'unclear')",
  "talking_points": "1-3 things worth bringing up next time"
}

Be concise. Keep each field under 250 characters. If the snippet is too \
short or unclear to extract a field, say 'unclear' or 'none' rather than \
inventing content."""


def _strip_json_fences(text: str) -> str:
    """Strip ```json ... ``` fences if the model added them despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence + optional language tag
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_memory(
    raw_text: str,
    source_type: str,
    caller_context: str = "",
) -> dict:
    """Extract structured memory from raw conversation text.

    Returns: {summary, commitments, cares_about, talking_points}
    Each field is a string (never None). Falls back to 'unclear' on
    extraction failure.
    """
    settings = Settings()
    if not settings.anthropic_api_key:
        raise ValueError("anthropic_api_key not configured")

    user_message_parts = [f"Source type: {source_type}"]
    if caller_context:
        user_message_parts.append(f"Caller context: {caller_context}")
    user_message_parts.append(f"Conversation snippet:\n\n{raw_text}")
    user_message = "\n\n".join(user_message_parts)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        timeout=30.0,
    )

    raw = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            "memory_extraction.parse_failed raw=%s error=%s",
            cleaned[:200], str(e)[:100],
        )
        # Fallback: return raw text as summary so the memory row isn't lost
        return {
            "summary": raw_text[:250],
            "commitments": "unclear",
            "cares_about": "unclear",
            "talking_points": "unclear",
        }

    # Normalize: ensure all 4 fields are present strings
    return {
        "summary": str(parsed.get("summary") or "unclear")[:1000],
        "commitments": str(parsed.get("commitments") or "none")[:1000],
        "cares_about": str(parsed.get("cares_about") or "unclear")[:1000],
        "talking_points": str(parsed.get("talking_points") or "unclear")[:1000],
    }
