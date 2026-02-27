"""AI-powered transaction categorization using Claude."""

import json
import logging
from typing import Optional

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import ExpenseCategory
from app.config import Settings
from app.core.exceptions import ValidationError

from .models import PlaidConnection, PlaidTransaction

logger = logging.getLogger(__name__)


async def _get_categories(db: AsyncSession) -> list[dict]:
    """Fetch all expense categories as a list of dicts."""
    result = await db.execute(
        select(ExpenseCategory).order_by(ExpenseCategory.name)
    )
    categories = result.scalars().all()
    return [{"id": str(c.id), "name": c.name} for c in categories]


async def ai_categorize_transactions(
    db: AsyncSession,
    user_id: str,
    settings: Settings,
    limit: int = 50,
) -> int:
    """Use Claude to categorize uncategorized bank transactions.

    Sends a batch of transactions to Claude with the available expense
    categories and asks it to assign the best-fit category for each.

    Returns the number of transactions categorized.
    """
    if not settings.anthropic_api_key:
        raise ValidationError(
            "Anthropic API key is not configured. Set ANTHROPIC_API_KEY in your environment."
        )

    # Fetch categories
    categories = await _get_categories(db)
    if not categories:
        raise ValidationError("No expense categories exist. Create categories first.")

    # Fetch uncategorized transactions
    txn_result = await db.execute(
        select(PlaidTransaction)
        .join(PlaidConnection, PlaidTransaction.plaid_connection_id == PlaidConnection.id)
        .where(
            PlaidConnection.user_id == user_id,
            PlaidTransaction.is_categorized.is_(False),
            PlaidTransaction.is_income.is_(False),
        )
        .order_by(PlaidTransaction.date.desc())
        .limit(limit)
    )
    transactions = list(txn_result.scalars().all())

    if not transactions:
        return 0

    # Build prompt
    category_list = "\n".join(f'- {c["id"]}: {c["name"]}' for c in categories)
    txn_list = []
    for t in transactions:
        txn_list.append({
            "id": str(t.id),
            "name": t.name,
            "merchant": t.merchant_name or "",
            "amount": t.amount,
            "date": str(t.date),
            "plaid_category": t.category or "",
        })

    prompt = f"""You are a bookkeeping assistant. Categorize each bank transaction into the most appropriate expense category.

Available categories:
{category_list}

Transactions to categorize:
{json.dumps(txn_list, indent=2)}

Return a JSON array of objects with "id" (transaction id) and "category_id" (the best matching category id from the list above). If you're not confident about a transaction, set "category_id" to null.

Return ONLY the JSON array, no other text."""

    # Call Claude
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    try:
        results = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse AI categorization response: %s", raw_text[:500])
        return 0

    # Apply results
    # Build lookup maps
    txn_map = {str(t.id): t for t in transactions}
    valid_category_ids = {c["id"] for c in categories}
    categorized_count = 0

    for item in results:
        txn_id = item.get("id")
        cat_id = item.get("category_id")

        if not txn_id or not cat_id:
            continue
        if cat_id not in valid_category_ids:
            continue

        txn = txn_map.get(txn_id)
        if txn and not txn.is_categorized:
            txn.category = next(
                (c["name"] for c in categories if c["id"] == cat_id), txn.category
            )
            txn.is_categorized = True
            categorized_count += 1

    await db.commit()

    logger.info(
        "AI categorized %d of %d transactions", categorized_count, len(transactions)
    )
    return categorized_count
