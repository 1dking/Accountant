"""Business logic for the AI module -- receipt/invoice extraction via Claude Vision."""

from __future__ import annotations

import base64
import io
import json
import logging
import time
import uuid

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import RECEIPT_EXTRACTION_PROMPT
from app.ai.schemas import ReceiptExtractionResult
from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.documents.models import Document
from app.documents.storage import StorageBackend

logger = logging.getLogger(__name__)

# MIME types that Claude Vision can process directly
VISION_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PDF_MIME_TYPE = "application/pdf"
EXTRACTABLE_MIME_TYPES = VISION_MIME_TYPES | {PDF_MIME_TYPE}


def _pdf_first_page_to_png(file_data: bytes) -> bytes:
    """Convert the first page of a PDF to a PNG image."""
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(file_data, first_page=1, last_page=1, dpi=200)
        if not images:
            raise ValidationError("Could not convert PDF to image.")
        buf = io.BytesIO()
        images[0].save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        raise ValidationError(
            "PDF extraction requires poppler to be installed. "
            "Install poppler-utils (apt) or poppler (brew/choco)."
        )


async def extract_receipt_data(
    file_data: bytes,
    mime_type: str,
    settings: Settings,
) -> ReceiptExtractionResult:
    """Send a document image to Claude Vision and parse the structured extraction."""

    if not settings.anthropic_api_key:
        raise ValidationError("Anthropic API key is not configured. Set ANTHROPIC_API_KEY in your environment.")

    if mime_type not in EXTRACTABLE_MIME_TYPES:
        raise ValidationError(
            f"File type '{mime_type}' is not supported for AI extraction. "
            f"Supported types: images (PNG, JPEG, WebP, GIF) and PDF."
        )

    # Convert PDF to image
    image_data = file_data
    image_mime = mime_type
    if mime_type == PDF_MIME_TYPE:
        image_data = _pdf_first_page_to_png(file_data)
        image_mime = "image/png"

    # Base64-encode
    b64_data = base64.standard_b64encode(image_data).decode("utf-8")

    # Call Claude Vision
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": RECEIPT_EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    # Parse the response
    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse AI extraction response as JSON: %s", raw_text[:500])
        # Return a minimal result with the raw text as full_text
        return ReceiptExtractionResult(full_text=raw_text)

    return ReceiptExtractionResult.model_validate(parsed)


async def process_document_ai(
    db: AsyncSession,
    storage: StorageBackend,
    document_id: uuid.UUID,
    settings: Settings,
) -> tuple[Document, ReceiptExtractionResult]:
    """Read a document from storage, extract data with AI, and update the document record."""

    start_time = time.monotonic()

    # Fetch document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document", str(document_id))

    # Read file from storage
    file_data = await storage.read(document.storage_path)

    # Extract
    extraction = await extract_receipt_data(file_data, document.mime_type, settings)

    # Update document with extraction results
    document.extracted_text = extraction.full_text or None
    document.extracted_metadata = extraction.model_dump(mode="json")

    await db.commit()
    await db.refresh(document)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    logger.info("AI extraction for document %s completed in %d ms", document_id, elapsed_ms)

    return document, extraction
