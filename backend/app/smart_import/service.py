"""Smart Import business logic."""

import json
import logging
import os
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


async def process_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    file_data: bytes,
    mime_type: str,
) -> SmartImport:
    """Process an uploaded file with AI to extract transactions."""
    import anthropic

    result = await db.execute(
        select(SmartImport).where(SmartImport.id == import_id)
    )
    imp = result.scalar_one_or_none()
    if not imp:
        raise NotFoundError("SmartImport", str(import_id))

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
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        # Parse response
        response_text = response.content[0].text
        # Try to extract JSON from the response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(response_text[json_start:json_end])
        else:
            raise ValueError("No JSON found in response")

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
        imp.status = ImportStatus.FAILED.value
        imp.error_message = str(e)[:500]
        imp.processing_time_ms = int((time.monotonic() - start) * 1000)
        await db.commit()
        await db.refresh(imp)

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
    from app.cashbook.models import EntryType

    imp = await get_import(db, import_id, user_id)

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

            entry_data = CashbookEntryCreate(
                account_id=account_id,
                entry_type=EntryType(item.entry_type),
                date=entry_date,
                description=item.description,
                total_amount=item.amount,
                tax_amount=item.tax_amount,
                tax_override=item.tax_amount is not None,
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
