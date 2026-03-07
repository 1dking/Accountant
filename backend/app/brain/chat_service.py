"""O-Brain chat service — streaming responses with tool use."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

import anthropic
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import (
    BrainConversation,
    BrainMessage,
    BrainAuditLog,
    AuditActionType,
)
from app.brain.tools import TOOL_DEFINITIONS, execute_tool
from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

SYSTEM_PROMPT_TEMPLATE = """You are O-Brain, the AI business assistant for {org_name}.
{brand_voice}

You have access to every invoice, contact, proposal, meeting transcript, email, and document in this business. Answer questions accurately using the data provided. When citing specifics (amounts, dates, names), be precise — you have real data, not guesses. If you don't have enough information, say so honestly and suggest how the user could add it.

Be warm, professional, and concise. Avoid unnecessary preambles.

Current context: {page_context}
Current date: {current_date}"""


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: str | None = None,
) -> BrainConversation:
    """Get existing or create new conversation."""
    if conversation_id:
        try:
            cid = uuid.UUID(conversation_id)
            stmt = select(BrainConversation).where(
                and_(BrainConversation.id == cid, BrainConversation.user_id == user_id)
            )
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv
        except (ValueError, Exception):
            pass

    conv = BrainConversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title="New conversation",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def check_rate_limit(db: AsyncSession, user_id: uuid.UUID) -> tuple[bool, int]:
    """Check if user is within rate limit. Returns (allowed, minutes_until_reset)."""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    stmt = select(func.count()).select_from(BrainMessage).where(
        and_(
            BrainMessage.role == "user",
            BrainMessage.created_at >= one_hour_ago,
        )
    ).join(BrainConversation).where(BrainConversation.user_id == user_id)

    result = await db.execute(stmt)
    count = result.scalar() or 0

    limit = settings.obrain_rate_limit_per_hour
    if count >= limit:
        # Find when the oldest message in the window will expire
        oldest_stmt = select(BrainMessage.created_at).join(BrainConversation).where(
            and_(
                BrainConversation.user_id == user_id,
                BrainMessage.role == "user",
                BrainMessage.created_at >= one_hour_ago,
            )
        ).order_by(BrainMessage.created_at).limit(1)
        oldest_result = await db.execute(oldest_stmt)
        oldest = oldest_result.scalar_one_or_none()
        if oldest:
            reset_time = oldest + timedelta(hours=1)
            minutes = max(1, int((reset_time - datetime.utcnow()).total_seconds() / 60))
            return False, minutes
        return False, 60
    return True, 0


async def _get_conversation_history(
    conversation: BrainConversation,
    max_messages: int = 20,
) -> list[dict]:
    """Get recent messages for context."""
    messages = conversation.messages or []
    recent = messages[-max_messages:]
    return [{"role": m.role, "content": m.content} for m in recent]


async def _get_org_context(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    """Get org name and brand voice."""
    from app.settings.models import CompanySettings
    from app.branding.models import BrandingSettings

    org_name = "your business"
    brand_voice = ""

    try:
        result = await db.execute(select(CompanySettings).limit(1))
        company = result.scalar_one_or_none()
        if company and company.company_name:
            org_name = company.company_name
    except Exception:
        pass

    try:
        result = await db.execute(select(BrandingSettings).limit(1))
        branding = result.scalar_one_or_none()
        if branding and branding.portal_welcome_message:
            brand_voice = f"Brand voice: {branding.portal_welcome_message}"
    except Exception:
        pass

    return org_name, brand_voice


async def chat_stream(
    db: AsyncSession,
    user_id: uuid.UUID,
    message: str,
    conversation_id: str | None = None,
    page_context: str = "General",
) -> AsyncGenerator[str, None]:
    """Stream a chat response using Claude with tool use.

    Yields SSE-formatted chunks:
      data: {"type": "text", "content": "..."}
      data: {"type": "tool_use", "tool": "...", "input": {...}}
      data: {"type": "sources", "sources": [...]}
      data: {"type": "done", "conversation_id": "...", "message_id": "..."}
    """
    # Rate limit check
    allowed, minutes = await check_rate_limit(db, user_id)
    if not allowed:
        rate_msg = "You've been busy! I need a short break — I'll be ready again in {} minutes. In the meantime, you can browse your data directly.".format(minutes)
        yield f'data: {json.dumps({"type": "text", "content": rate_msg})}\n\n'
        yield f'data: {json.dumps({"type": "done"})}\n\n'
        return

    # Get/create conversation
    conversation = await get_or_create_conversation(db, user_id, conversation_id)

    # Save user message
    user_msg = BrainMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(user_msg)
    await db.commit()

    # Auto-title from first message
    if conversation.title == "New conversation":
        conversation.title = message[:100] + ("..." if len(message) > 100 else "")
        await db.commit()

    # Build system prompt
    org_name, brand_voice = await _get_org_context(db, user_id)

    # Sanitize page_context to prevent prompt injection
    safe_context = (page_context or "General")[:200]
    # Remove any attempts to override instructions
    safe_context = safe_context.replace("\n", " ").replace("\r", " ")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        org_name=org_name,
        brand_voice=brand_voice,
        page_context=safe_context,
        current_date=datetime.utcnow().strftime("%Y-%m-%d"),
    )

    # Build conversation history
    history = await _get_conversation_history(conversation)
    # Remove the last message (the one we just added) since we'll add it fresh
    if history and history[-1]["content"] == message:
        history = history[:-1]

    messages = history + [{"role": "user", "content": message}]

    # Call Claude with tools
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    tools_used: list[str] = []
    sources: list[dict] = []
    full_response = ""

    try:
        # Streaming loop — every call uses true streaming so text arrives
        # token-by-token.  If Claude requests tool_use we collect the full
        # response, execute tools, and start a new streaming round.
        rounds = 0
        while rounds <= 3:
            rounds += 1

            async with client.messages.stream(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield f'data: {json.dumps({"type": "text", "content": text})}\n\n'

                response = await stream.get_final_message()

            # If Claude didn't request tools, we're done
            if response.stop_reason != "tool_use":
                break

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tools_used.append(tool_name)

                    yield f'data: {json.dumps({"type": "tool_use", "tool": tool_name})}\n\n'

                    result_str = await execute_tool(db, user_id, tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                    # Track sources
                    try:
                        result_data = json.loads(result_str)
                        if "count" in result_data:
                            sources.append({"tool": tool_name, "count": result_data["count"]})
                    except (json.JSONDecodeError, KeyError):
                        pass

            # Build next messages with tool results
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

    except anthropic.APIError as e:
        error_msg = "I'm having trouble connecting right now. Please try again in a moment."
        full_response = error_msg
        logger.error("Brain API error: %s", e.message)
        yield f'data: {json.dumps({"type": "text", "content": error_msg})}\n\n'
    except Exception as e:
        error_msg = "Something went wrong. Please try again."
        full_response = error_msg
        logger.exception("Brain chat error")
        yield f'data: {json.dumps({"type": "text", "content": error_msg})}\n\n'

    # Save assistant message
    assistant_msg = BrainMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        tools_used_json=json.dumps(tools_used) if tools_used else None,
        sources_cited_json=json.dumps(sources) if sources else None,
    )
    db.add(assistant_msg)
    await db.commit()

    # Audit log
    audit = BrainAuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        action_type=AuditActionType.CHAT_QUERY,
        ai_input=message,
        ai_output=full_response[:1000],
        source_data_json=json.dumps({"tools_used": tools_used, "sources": sources}),
    )
    db.add(audit)
    await db.commit()

    # Emit sources
    if sources:
        yield f'data: {json.dumps({"type": "sources", "sources": sources})}\n\n'

    # Done
    yield f'data: {json.dumps({"type": "done", "conversation_id": str(conversation.id), "message_id": str(assistant_msg.id)})}\n\n'


async def list_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[BrainConversation]:
    """List user's conversations, most recent first."""
    stmt = (
        select(BrainConversation)
        .where(BrainConversation.user_id == user_id)
        .order_by(desc(BrainConversation.updated_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> BrainConversation | None:
    """Get a single conversation with messages."""
    stmt = select(BrainConversation).where(
        and_(BrainConversation.id == conversation_id, BrainConversation.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    """Delete a conversation."""
    conv = await get_conversation(db, user_id, conversation_id)
    if not conv:
        return False
    await db.delete(conv)
    await db.commit()
    return True
