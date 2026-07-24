"""Input guards for vision/model calls.

``ai/service.py`` base64-encoded the raw uploaded file straight to Claude with
no size ceiling, no page ceiling and no downscaling, while ``max_upload_size``
allowed 100 MB. Claude bills a PDF **per page as an image**, so one automatic
upload could cost several dollars.

These guards bound the worst case *before* any token is spent.
"""

import io
import logging

from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

#: Hard ceiling on bytes handed to a vision call. Anything larger is refused
#: rather than silently costing a fortune. Well above a phone photo or a normal
#: receipt PDF, well below the 100 MB upload limit.
MAX_VISION_BYTES = 8 * 1024 * 1024  # 8 MB

#: Claude renders each PDF page as an image, so page count *is* cost. Beyond
#: this we extract the first N pages instead of the whole document.
MAX_PDF_PAGES = 5

#: Anthropic downscales images above ~1568px on the long edge anyway; doing it
#: ourselves makes the token cost predictable and cuts upload bandwidth.
MAX_IMAGE_EDGE = 1568

#: Deliberately NOT a byte threshold. Vision cost scales with PIXEL DIMENSIONS,
#: not file size — a 4032x3024 screenshot of flat colour compresses to ~180 KB
#: but still costs ~16k tokens. The decision to resize is made on dimensions
#: alone; Image.open() only reads the header, so this is cheap.


def check_vision_size(file_data: bytes, mime_type: str) -> None:
    """Refuse oversized input before any model call. Raises ValidationError."""
    if len(file_data) > MAX_VISION_BYTES:
        raise ValidationError(
            f"This file is {len(file_data) / 1024 / 1024:.1f} MB. AI extraction is limited to "
            f"{MAX_VISION_BYTES // 1024 // 1024} MB — upload a smaller file or extract it manually."
        )


def downscale_image(file_data: bytes, mime_type: str) -> tuple[bytes, str]:
    """Shrink an image to MAX_IMAGE_EDGE on its long edge.

    Returns ``(data, mime_type)``. Never raises: if Pillow is unavailable or
    the image is unreadable, the original bytes are returned so extraction
    still works — degraded cost, not a broken feature.
    """
    if mime_type == "application/pdf":
        return file_data, mime_type

    try:
        from PIL import Image
    except ModuleNotFoundError:
        logger.info("ai.guards: Pillow not installed — sending image at full resolution")
        return file_data, mime_type

    try:
        img = Image.open(io.BytesIO(file_data))
        if max(img.size) <= MAX_IMAGE_EDGE:
            return file_data, mime_type

        img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        out = buf.getvalue()

        if len(out) >= len(file_data):
            return file_data, mime_type

        logger.info(
            "ai.guards: downscaled image %d KB -> %d KB", len(file_data) // 1024, len(out) // 1024
        )
        return out, "image/jpeg"
    except Exception:  # noqa: BLE001 — never block extraction on a resize failure
        logger.exception("ai.guards: image downscale failed — using original")
        return file_data, mime_type


def cap_pdf_pages(file_data: bytes, mime_type: str, max_pages: int = MAX_PDF_PAGES) -> tuple[bytes, int]:
    """Trim a PDF to its first ``max_pages`` pages.

    Returns ``(data, page_count_sent)``. Falls back to the original bytes when
    pypdf is unavailable — the size ceiling is still the backstop.
    """
    if mime_type != "application/pdf":
        return file_data, 1

    # PyMuPDF is already a project dependency (pyproject: PyMuPDF>=1.24.0) —
    # deliberately not adding a new PDF library for this.
    try:
        import fitz
    except ModuleNotFoundError:
        logger.info("ai.guards: PyMuPDF not installed — cannot cap PDF pages")
        return file_data, -1

    doc = None
    out_doc = None
    try:
        doc = fitz.open(stream=file_data, filetype="pdf")
        total = doc.page_count
        if total <= max_pages:
            return file_data, total

        out_doc = fitz.open()
        out_doc.insert_pdf(doc, from_page=0, to_page=max_pages - 1)
        trimmed = out_doc.tobytes()
        logger.info("ai.guards: capped PDF from %d pages to %d", total, max_pages)
        return trimmed, max_pages
    except Exception:  # noqa: BLE001
        logger.exception("ai.guards: PDF page cap failed — using original")
        return file_data, -1
    finally:
        for d in (out_doc, doc):
            try:
                if d is not None:
                    d.close()
            except Exception:  # noqa: BLE001
                pass


def prepare_for_vision(file_data: bytes, mime_type: str) -> tuple[bytes, str, int]:
    """Apply every guard in order. Returns ``(data, mime_type, billable_units)``.

    ``billable_units`` is the page count for PDFs (1 for images) so the caller
    can charge the AI meter proportionally.
    """
    check_vision_size(file_data, mime_type)
    data, mime = downscale_image(file_data, mime_type)
    data, pages = cap_pdf_pages(data, mime)
    units = pages if pages > 0 else 1
    return data, mime, units
