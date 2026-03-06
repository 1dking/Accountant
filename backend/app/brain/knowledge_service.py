"""Knowledge base management — upload, embed, onboarding."""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import BrainEmbedding, EmbeddingSourceType
from app.brain.embedding_service import embed_and_store, delete_embeddings_for_source

logger = logging.getLogger(__name__)


async def add_knowledge(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    title: str = "",
    category: str = "general",
) -> dict:
    """Add a piece of knowledge to the brain (manual note, FAQ, brand info, etc.)."""
    source_id = str(uuid.uuid4())
    metadata = {"title": title, "category": category, "added_at": datetime.utcnow().isoformat()}

    await embed_and_store(
        db=db,
        user_id=user_id,
        content=content,
        source_type=EmbeddingSourceType.BRAND_KNOWLEDGE,
        source_id=source_id,
        metadata=metadata,
    )

    return {
        "source_id": source_id,
        "title": title,
        "category": category,
        "chunk_count": max(1, len(content) // 2000),
    }


async def list_knowledge(
    db: AsyncSession,
    user_id: uuid.UUID,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List knowledge base items (grouped by source_id)."""
    stmt = select(
        BrainEmbedding.source_id,
        BrainEmbedding.metadata_json,
        func.count().label("chunk_count"),
        func.min(BrainEmbedding.created_at).label("created_at"),
    ).where(
        and_(
            BrainEmbedding.user_id == user_id,
            BrainEmbedding.source_type == EmbeddingSourceType.BRAND_KNOWLEDGE,
        )
    ).group_by(
        BrainEmbedding.source_id, BrainEmbedding.metadata_json,
    ).order_by(
        func.min(BrainEmbedding.created_at).desc()
    ).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    rows = result.all()

    # Count total
    count_stmt = select(
        func.count(func.distinct(BrainEmbedding.source_id))
    ).where(
        and_(
            BrainEmbedding.user_id == user_id,
            BrainEmbedding.source_type == EmbeddingSourceType.BRAND_KNOWLEDGE,
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    items = []
    for row in rows:
        meta = {}
        if row.metadata_json:
            try:
                meta = json.loads(row.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass
        item_cat = meta.get("category", "general")
        if category and item_cat != category:
            continue
        items.append({
            "source_id": row.source_id,
            "title": meta.get("title", "Untitled"),
            "category": item_cat,
            "chunk_count": row.chunk_count,
            "created_at": str(row.created_at) if row.created_at else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def delete_knowledge(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_id: str,
) -> bool:
    """Delete a knowledge base item (all chunks)."""
    count = await delete_embeddings_for_source(
        db=db,
        user_id=user_id,
        source_type=EmbeddingSourceType.BRAND_KNOWLEDGE,
        source_id=source_id,
    )
    return count > 0


async def process_onboarding_answers(
    db: AsyncSession,
    user_id: uuid.UUID,
    answers: list[dict],
) -> int:
    """Process guided onboarding answers and store as brand knowledge.

    Each answer: {"question": str, "answer": str}
    """
    stored = 0
    for item in answers:
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        if not answer:
            continue

        content = f"Q: {question}\nA: {answer}"
        await add_knowledge(
            db=db,
            user_id=user_id,
            content=content,
            title=question[:100],
            category="onboarding",
        )
        stored += 1

    return stored


ONBOARDING_QUESTIONS = [
    {
        "id": "business_description",
        "question": "Describe your business in a few sentences. What do you do, and who are your customers?",
        "placeholder": "We are a digital marketing agency serving small businesses...",
    },
    {
        "id": "services",
        "question": "What are your main services or products and their typical price ranges?",
        "placeholder": "Web design ($2,000-$10,000), SEO ($500/month)...",
    },
    {
        "id": "team",
        "question": "How is your team structured? Key roles and responsibilities?",
        "placeholder": "3 designers, 2 developers, 1 project manager...",
    },
    {
        "id": "processes",
        "question": "What are your key business processes? (e.g., onboarding flow, project lifecycle)",
        "placeholder": "Client onboarding takes 2 weeks, projects run in 2-week sprints...",
    },
    {
        "id": "tone",
        "question": "How would you describe your brand voice and communication style?",
        "placeholder": "Professional but friendly, we use first names...",
    },
    {
        "id": "goals",
        "question": "What are your current business goals or challenges?",
        "placeholder": "Growing to $1M ARR, reducing client churn...",
    },
    {
        "id": "policies",
        "question": "Any specific policies O-Brain should know about? (payment terms, refund policy, etc.)",
        "placeholder": "Net 30 payment terms, 50% deposit required...",
    },
]


def get_onboarding_questions() -> list[dict]:
    """Return the onboarding question set."""
    return ONBOARDING_QUESTIONS
