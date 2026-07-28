"""Smart Import business logic."""

import json
import logging
import os
import re
import time
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.smart_import.models import (
    ImportItemStatus,
    ImportStatus,
    SmartImport,
    SmartImportItem,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


async def create_import(
    db: AsyncSession,
    user: User,
    filename: str,
    storage_path: str,
    mime_type: str,
    file_size: int,
) -> SmartImport:
    """Create a new smart import record."""
    imp = SmartImport(
        id=uuid.uuid4(),
        user_id=user.id,
        original_filename=filename,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size=file_size,
        status=ImportStatus.PENDING.value,
    )
    db.add(imp)
    await db.commit()
    await db.refresh(imp)
    return imp


def _parse_ai_json(response) -> dict:
    """Extract the transactions JSON from an Anthropic response, robustly.

    Handles markdown ```json fences, prose around the JSON, multiple text
    blocks, and output truncated by the token limit — the latter surfaced as a
    clear, actionable error instead of a cryptic JSON parse failure (the old
    ``content[0].text`` + brace-slice turned any of these into a hard failure
    with zero extracted rows)."""
    text = "".join(
        getattr(b, "text", "") for b in response.content
        if getattr(b, "type", None) == "text"
    ).strip()

    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ValueError(
            "This statement has more rows than can be read in a single pass. "
            "Upload a CSV export of it instead, or split the file into smaller parts."
        )
    if not text:
        raise ValueError("The AI returned no readable text for this document.")

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}") + 1
    if 0 <= start < end:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    raise ValueError(
        "The document was read but the result could not be parsed. "
        "If it is a statement with many rows, try a CSV export instead."
    )


def _decode_csv_bytes(data: bytes) -> str:
    """Decode CSV bytes, tolerating a BOM and non-UTF-8 exports."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


async def process_csv_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    file_data: bytes,
) -> SmartImport:
    """Parse a CSV statement/export deterministically — no AI call, no credits.

    Same output shape as ``process_import`` so the review/confirm flow is
    identical; this path is exact and free, ideal for provider exports (Meta
    Ads, Stripe, bank CSVs)."""
    from app.smart_import.csv_parser import parse_statement_csv

    result = await db.execute(select(SmartImport).where(SmartImport.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise NotFoundError("SmartImport", str(import_id))

    imp.status = ImportStatus.PROCESSING.value
    await db.commit()

    start = time.monotonic()
    try:
        text = _decode_csv_bytes(file_data)
        parsed = parse_statement_csv(text, imp.original_filename or "")

        imp.document_type = parsed["document_type"]
        imp.ai_summary = parsed["summary"]

        transactions = parsed["transactions"]
        for tx in transactions:
            db.add(SmartImportItem(
                id=uuid.uuid4(),
                import_id=imp.id,
                entry_type=tx.get("entry_type", "expense"),
                date=tx.get("date"),
                description=(tx.get("description") or "Transaction")[:500],
                amount=float(tx.get("amount", 0)),
                tax_amount=float(tx["tax_amount"]) if tx.get("tax_amount") else None,
                category_suggestion=tx.get("category_suggestion"),
                confidence=1.0,  # deterministic parse — not a guess
                raw_data=json.dumps(tx),
            ))

        if transactions:
            imp.status = ImportStatus.READY.value
        else:
            # Explain WHY nothing was read instead of a silent empty result.
            imp.status = ImportStatus.FAILED.value
            imp.error_message = parsed["summary"]
        imp.processing_time_ms = int((time.monotonic() - start) * 1000)
        await db.commit()
        await db.refresh(imp, attribute_names=["items"])
    except Exception as e:
        logger.exception("Smart import CSV processing failed for %s", import_id)
        try:
            await db.rollback()
        except Exception:
            pass
        try:
            result = await db.execute(select(SmartImport).where(SmartImport.id == import_id))
            imp = result.scalar_one_or_none()
            if imp:
                imp.status = ImportStatus.FAILED.value
                imp.error_message = f"Could not read this CSV: {str(e)[:300]}"
                imp.processing_time_ms = int((time.monotonic() - start) * 1000)
                await db.commit()
                await db.refresh(imp)
        except Exception:
            logger.warning("Failed to save CSV error state for %s", import_id, exc_info=True)

    return imp


async def process_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    file_data: bytes,
    mime_type: str,
) -> SmartImport:
    """Process an uploaded file with AI to extract transactions."""
    import anthropic

    from app.billing.ai_meter import safe_consume_by_user_id

    result = await db.execute(
        select(SmartImport).where(SmartImport.id == import_id)
    )
    imp = result.scalar_one_or_none()
    if not imp:
        raise NotFoundError("SmartImport", str(import_id))

    # Charge the AI meter before the model call. Refusing here costs the user
    # an error; refusing after the call costs us the tokens.
    if not await safe_consume_by_user_id(db, imp.user_id, "smart_import"):
        imp.status = ImportStatus.FAILED.value
        imp.error_message = (
            "Out of AI credits for this month. Upgrade your plan to run more imports."
        )
        await db.commit()
        return imp

    imp.status = ImportStatus.PROCESSING.value
    await db.commit()

    start = time.monotonic()

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Build the message content
        content = []
        image_types = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        if mime_type in image_types:
            import base64
            b64 = base64.b64encode(file_data).decode()
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": b64},
            })
        elif mime_type == "application/pdf":
            import base64
            b64 = base64.b64encode(file_data).decode()
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })

        content.append({
            "type": "text",
            "text": """Analyze this financial document and extract ALL transactions or line items.

IMPORTANT: If this is a multi-line invoice, annual bill, or statement with multiple line items,
extract EACH line item as a SEPARATE transaction. For example:
- An annual invoice with 12 monthly charges → 12 separate transactions (one per month)
- A bill with itemized services (web hosting, domain, SSL, etc.) → one transaction per service
- A bank/credit card statement → one transaction per line
- A receipt with multiple distinct items → one transaction per item
Do NOT collapse multiple line items into a single total. Extract every individual charge.

For each transaction, provide:
- entry_type: "income" or "expense"
- date: ISO format (YYYY-MM-DD) if visible. For recurring/monthly items, assign the appropriate month date.
- description: brief description of the transaction (include the vendor/source name)
- amount: the amount for THIS line item only (positive number)
- tax_amount: tax amount if separately shown for this item (or null)
- category_suggestion: suggest a category from: Advertising, Inventory, Shipping, Fuel, Meals, Office Supplies, Professional Fees, Rent, Repairs & Maintenance, Travel, Utilities, Dues & Subscriptions, Education & Training, Insurance, Fees, Grant, Rental Income, Other Income, Other Expense

Also provide:
- document_type: "receipt", "invoice", "bank_statement", "credit_card_statement", or "other"
- summary: a brief 1-sentence summary of the document

Return ONLY valid JSON in this exact format:
{
  "document_type": "invoice",
  "summary": "Annual hosting invoice from GoDaddy with 12 monthly charges",
  "transactions": [
    {
      "entry_type": "expense",
      "date": "2024-01-15",
      "description": "GoDaddy Web Hosting - January 2024",
      "amount": 29.99,
      "tax_amount": 3.90,
      "category_suggestion": "Dues & Subscriptions"
    },
    {
      "entry_type": "expense",
      "date": "2024-02-15",
      "description": "GoDaddy Web Hosting - February 2024",
      "amount": 29.99,
      "tax_amount": 3.90,
      "category_suggestion": "Dues & Subscriptions"
    }
  ]
}""",
        })

        response = await client.messages.create(
            model=settings.anthropic_model,
            # Raised from 4096: a statement with many rows produces long JSON,
            # and truncation there silently failed the whole import.
            max_tokens=8192,
            messages=[{"role": "user", "content": content}],
        )

        data = _parse_ai_json(response)

        # Re-fetch imp in a clean transaction to avoid stale-state UPDATE failures
        await db.rollback()
        result = await db.execute(
            select(SmartImport).where(SmartImport.id == import_id)
        )
        imp = result.scalar_one_or_none()
        if not imp:
            raise NotFoundError("SmartImport", str(import_id))

        imp.document_type = data.get("document_type", "other")
        imp.ai_summary = data.get("summary", "")

        transactions = data.get("transactions", [])
        for tx in transactions:
            item = SmartImportItem(
                id=uuid.uuid4(),
                import_id=imp.id,
                entry_type=tx.get("entry_type", "expense"),
                date=tx.get("date"),
                description=tx.get("description", "Unknown transaction"),
                amount=float(tx.get("amount", 0)),
                tax_amount=float(tx["tax_amount"]) if tx.get("tax_amount") else None,
                category_suggestion=tx.get("category_suggestion"),
                confidence=0.85,  # Default confidence for AI extraction
                raw_data=json.dumps(tx),
            )
            db.add(item)

        imp.status = ImportStatus.READY.value
        imp.processing_time_ms = int((time.monotonic() - start) * 1000)
        await db.commit()
        await db.refresh(imp, attribute_names=["items"])

    except Exception as e:
        logger.exception("Smart import processing failed for %s", import_id)
        # Rollback to clear any pending flush errors before saving error state
        try:
            await db.rollback()
        except Exception:
            pass
        try:
            result = await db.execute(
                select(SmartImport).where(SmartImport.id == import_id)
            )
            imp = result.scalar_one_or_none()
            if imp:
                imp.status = ImportStatus.FAILED.value
                imp.error_message = str(e)[:500]
                imp.processing_time_ms = int((time.monotonic() - start) * 1000)
                await db.commit()
                await db.refresh(imp)
        except Exception:
            logger.warning("Failed to save error state for import %s", import_id, exc_info=True)

    return imp


async def get_import(db: AsyncSession, import_id: uuid.UUID, user_id: uuid.UUID) -> SmartImport:
    """Get a smart import with its items."""
    result = await db.execute(
        select(SmartImport)
        .options(selectinload(SmartImport.items))
        .where(SmartImport.id == import_id, SmartImport.user_id == user_id)
    )
    imp = result.scalar_one_or_none()
    if not imp:
        raise NotFoundError("SmartImport", str(import_id))
    return imp


async def list_imports(db: AsyncSession, user_id: uuid.UUID) -> list[SmartImport]:
    """List all imports for a user."""
    result = await db.execute(
        select(SmartImport)
        .options(selectinload(SmartImport.items))
        .where(SmartImport.user_id == user_id)
        .order_by(SmartImport.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().unique().all())


async def update_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    **updates: object,
) -> SmartImportItem:
    """Update a single import item."""
    result = await db.execute(
        select(SmartImportItem)
        .join(SmartImport)
        .where(SmartImportItem.id == item_id, SmartImport.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("SmartImportItem", str(item_id))

    for field, value in updates.items():
        if value is not None:
            setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


async def delete_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete an import and its associated cashbook entries."""
    from app.cashbook.models import CashbookEntry
    from sqlalchemy import delete as sa_delete

    imp = await get_import(db, import_id, user_id)

    # Delete linked cashbook entries
    entry_ids = [
        item.cashbook_entry_id for item in imp.items
        if item.cashbook_entry_id is not None
    ]
    if entry_ids:
        await db.execute(
            sa_delete(CashbookEntry).where(CashbookEntry.id.in_(entry_ids))
        )

    # Delete the import (cascade deletes items)
    await db.delete(imp)
    await db.commit()


async def delete_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a single import item from review."""
    result = await db.execute(
        select(SmartImportItem)
        .join(SmartImport)
        .where(SmartImportItem.id == item_id, SmartImport.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("SmartImportItem", str(item_id))

    await db.delete(item)
    await db.commit()


async def confirm_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    item_ids: list[uuid.UUID] | None = None,
) -> dict:
    """Confirm and create cashbook entries from approved import items."""
    from app.cashbook.service import create_entry
    from app.cashbook.schemas import CashbookEntryCreate
    from app.cashbook.models import EntryType, TransactionCategory

    imp = await get_import(db, import_id, user_id)

    # Resolve category-name suggestions (e.g. "Advertising") to real
    # transaction-category ids once, so the suggestion actually sticks on the
    # posted entry instead of being dropped.
    cat_rows = (await db.execute(select(TransactionCategory))).scalars().all()
    cat_by_name = {c.name.strip().lower(): c.id for c in cat_rows}

    # Get user object
    from app.auth.models import User as UserModel
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = user_result.scalar_one()

    items_to_import = [
        item for item in imp.items
        if item.status in (ImportItemStatus.APPROVED.value, ImportItemStatus.PENDING.value)
        and (item_ids is None or item.id in item_ids)
    ]

    imported_count = 0
    errors = []

    for item in items_to_import:
        try:
            entry_date = date.today()
            if item.date:
                try:
                    entry_date = date.fromisoformat(item.date)
                except ValueError:
                    pass

            category_id = None
            if item.category_suggestion:
                category_id = cat_by_name.get(item.category_suggestion.strip().lower())

            entry_data = CashbookEntryCreate(
                account_id=account_id,
                entry_type=EntryType(item.entry_type),
                date=entry_date,
                description=item.description,
                total_amount=item.amount,
                tax_amount=item.tax_amount,
                tax_override=item.tax_amount is not None,
                category_id=category_id,
                source="smart_import",
                source_id=str(item.id),
            )

            entry = await create_entry(db, entry_data, user)
            item.status = ImportItemStatus.IMPORTED.value
            item.cashbook_entry_id = entry.id
            imported_count += 1

        except Exception as e:
            errors.append(f"{item.description}: {str(e)[:100]}")
            logger.warning("Failed to import item %s: %s", item.id, e)
            try:
                await db.rollback()
            except Exception:
                pass

    # Update import status
    all_imported = all(
        item.status in (ImportItemStatus.IMPORTED.value, ImportItemStatus.REJECTED.value, ImportItemStatus.DUPLICATE.value)
        for item in imp.items
    )
    imp.status = ImportStatus.IMPORTED.value if all_imported else ImportStatus.PARTIALLY_IMPORTED.value
    await db.commit()

    return {
        "imported_count": imported_count,
        "total_items": len(items_to_import),
        "errors": errors,
    }
