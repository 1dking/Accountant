"""Embedding service — OpenAI text-embedding-3-small with TF-IDF fallback."""

import json
import logging
import math
import re
import uuid
from collections import Counter

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.models import BrainEmbedding, EmbeddingSourceType
from app.config import Settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536
CHUNK_SIZE = 500  # tokens (approx 4 chars per token)
CHUNK_OVERLAP = 100

# Relevance weights by source type
RELEVANCE_WEIGHTS: dict[str, float] = {
    "meeting_transcript": 1.5,
    "call_transcript": 1.5,
    "brand_knowledge": 2.0,
    "meeting_notes": 1.3,
    "call_notes": 1.3,
    "email": 1.0,
    "document": 1.0,
    "sms": 0.7,
    "manual_note": 1.2,
    "form_response": 1.0,
    "internal_comment": 1.0,
}

settings = Settings()

# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def _approx_token_count(text_: str) -> int:
    """Approximate token count (1 token ~= 4 chars)."""
    return len(text_) // 4


def chunk_text(text_: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by approximate token count."""
    if not text_ or not text_.strip():
        return []

    # Split on sentence boundaries where possible
    sentences = re.split(r'(?<=[.!?])\s+', text_.strip())
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _approx_token_count(sentence)

        if current_tokens + sentence_tokens > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap
            overlap_text = " ".join(current_chunk)
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_chunk):
                t = _approx_token_count(s)
                if overlap_tokens + t > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += t
            current_chunk = overlap_sentences
            current_tokens = overlap_tokens

        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # If no sentence boundaries found, split by character
    if not chunks and text_.strip():
        char_size = chunk_size * 4
        char_overlap = overlap * 4
        for i in range(0, len(text_), char_size - char_overlap):
            chunks.append(text_[i:i + char_size])

    return chunks


# ---------------------------------------------------------------------------
# OpenAI embedding
# ---------------------------------------------------------------------------

async def _embed_openai(texts: list[str]) -> list[list[float]]:
    """Get embeddings from OpenAI text-embedding-3-small."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # OpenAI batch limit is 2048
    all_embeddings: list[list[float]] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        for item in response.data:
            all_embeddings.append(item.embedding)

    return all_embeddings


# ---------------------------------------------------------------------------
# TF-IDF fallback (no API key needed)
# ---------------------------------------------------------------------------

def _tfidf_embed(texts: list[str]) -> list[list[float]]:
    """Simple TF-IDF-based embedding fallback when no OpenAI key is set."""
    # Build vocabulary from all texts
    all_words: set[str] = set()
    doc_words: list[list[str]] = []
    for t in texts:
        words = re.findall(r'\w+', t.lower())
        doc_words.append(words)
        all_words.update(words)

    vocab = sorted(all_words)[:EMBEDDING_DIM]
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    doc_count = len(texts)

    # IDF
    df: Counter = Counter()
    for words in doc_words:
        seen = set(words)
        for w in seen:
            if w in word_to_idx:
                df[w] += 1

    embeddings: list[list[float]] = []
    for words in doc_words:
        vec = [0.0] * EMBEDDING_DIM
        tf = Counter(words)
        total = len(words) or 1
        for w, count in tf.items():
            if w in word_to_idx:
                idx = word_to_idx[w]
                idf = math.log((doc_count + 1) / (df.get(w, 0) + 1)) + 1
                vec[idx] = (count / total) * idf

        # Normalize
        magnitude = math.sqrt(sum(v * v for v in vec)) or 1.0
        vec = [v / magnitude for v in vec]
        embeddings.append(vec)

    return embeddings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI or TF-IDF fallback."""
    if not texts:
        return []

    if settings.openai_api_key:
        try:
            return await _embed_openai(texts)
        except Exception as e:
            logger.warning("OpenAI embedding failed, falling back to TF-IDF: %s", e)

    return _tfidf_embed(texts)


async def embed_and_store(
    db: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    source_type: EmbeddingSourceType,
    source_id: str | None = None,
    contact_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> list[BrainEmbedding]:
    """Chunk text, embed, and store in brain_embeddings."""
    chunks = chunk_text(content)
    if not chunks:
        return []

    embeddings = await embed_texts(chunks)
    weight = RELEVANCE_WEIGHTS.get(source_type.value, 1.0)
    meta_str = json.dumps(metadata) if metadata else None

    records: list[BrainEmbedding] = []
    for chunk_text_, embedding in zip(chunks, embeddings):
        record = BrainEmbedding(
            id=uuid.uuid4(),
            user_id=user_id,
            content=chunk_text_,
            embedding_json=json.dumps(embedding),
            source_type=source_type,
            source_id=source_id,
            contact_id=contact_id,
            relevance_weight=weight,
            metadata_json=meta_str,
        )
        db.add(record)
        records.append(record)

    await db.commit()
    return records


async def delete_embeddings_for_source(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_type: EmbeddingSourceType,
    source_id: str,
) -> int:
    """Delete all embeddings for a specific source."""
    from sqlalchemy import delete, and_

    stmt = delete(BrainEmbedding).where(
        and_(
            BrainEmbedding.user_id == user_id,
            BrainEmbedding.source_type == source_type,
            BrainEmbedding.source_id == source_id,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
