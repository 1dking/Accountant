"""Retrieval service — hybrid vector similarity + keyword search."""

import json
import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import BrainEmbedding, EmbeddingSourceType
from app.brain.embedding_service import embed_texts

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    content: str
    source_type: str
    source_id: str | None
    contact_id: str | None
    relevance_score: float
    metadata: dict | None


async def search_brain(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    source_types: list[str] | None = None,
    contact_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    """Hybrid search: vector similarity + keyword matching.

    Combines cosine similarity from embeddings with BM25-style keyword
    scoring for better results on exact terms.
    """
    # Get all candidate embeddings for the user
    conditions = [BrainEmbedding.user_id == user_id]
    if source_types:
        type_enums = []
        for st in source_types:
            try:
                type_enums.append(EmbeddingSourceType(st))
            except ValueError:
                pass
        if type_enums:
            conditions.append(BrainEmbedding.source_type.in_(type_enums))
    if contact_id:
        conditions.append(BrainEmbedding.contact_id == contact_id)

    stmt = select(BrainEmbedding).where(and_(*conditions)).limit(2000)
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    if not candidates:
        return []

    # Embed the query
    query_embeddings = await embed_texts([query])
    if not query_embeddings:
        return []
    query_vec = query_embeddings[0]

    # Score each candidate: cosine similarity × relevance_weight + keyword_bonus
    query_terms = set(re.findall(r'\w+', query.lower()))
    scored: list[tuple[BrainEmbedding, float]] = []

    for emb in candidates:
        # Cosine similarity
        if emb.embedding_json:
            try:
                emb_vec = json.loads(emb.embedding_json)
                dot = sum(a * b for a, b in zip(query_vec, emb_vec))
                mag_q = sum(a * a for a in query_vec) ** 0.5
                mag_e = sum(a * a for a in emb_vec) ** 0.5
                cosine = dot / (mag_q * mag_e) if mag_q and mag_e else 0.0
            except (json.JSONDecodeError, TypeError):
                cosine = 0.0
        else:
            cosine = 0.0

        # Keyword bonus (BM25-lite)
        content_terms = set(re.findall(r'\w+', emb.content.lower()))
        matched = query_terms & content_terms
        keyword_bonus = len(matched) / max(len(query_terms), 1) * 0.3

        # Final score with relevance weight
        score = (cosine + keyword_bonus) * emb.relevance_weight
        scored.append((emb, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    results: list[SearchResult] = []
    for emb, score in scored[:limit]:
        meta = None
        if emb.metadata_json:
            try:
                meta = json.loads(emb.metadata_json)
            except json.JSONDecodeError:
                pass

        results.append(SearchResult(
            content=emb.content,
            source_type=emb.source_type.value if isinstance(emb.source_type, EmbeddingSourceType) else str(emb.source_type),
            source_id=emb.source_id,
            contact_id=str(emb.contact_id) if emb.contact_id else None,
            relevance_score=round(score, 4),
            metadata=meta,
        ))

    return results


async def search_by_type(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    source_type: str,
    contact_id: uuid.UUID | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    """Convenience wrapper to search within a specific source type."""
    return await search_brain(
        db, user_id, query,
        source_types=[source_type],
        contact_id=contact_id,
        limit=limit,
    )
