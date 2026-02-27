
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.models import Expense
from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError

from .categorization_models import CategorizationRule, MatchField, MatchType
from .models import PlaidConnection, PlaidTransaction
from .schemas import CategorizationRuleCreate, CategorizationRuleUpdate


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------


async def list_rules(db: AsyncSession) -> list[CategorizationRule]:
    """List all categorization rules ordered by priority (highest first)."""
    result = await db.execute(
        select(CategorizationRule).order_by(
            CategorizationRule.priority.desc(),
            CategorizationRule.created_at.asc(),
        )
    )
    return list(result.scalars().all())


async def get_rule(
    db: AsyncSession, rule_id: uuid.UUID
) -> CategorizationRule:
    result = await db.execute(
        select(CategorizationRule).where(CategorizationRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Categorization rule", str(rule_id))
    return rule


async def create_rule(
    db: AsyncSession, data: CategorizationRuleCreate, user: User
) -> CategorizationRule:
    """Create a new categorization rule."""
    # Validate enum values
    try:
        match_field = MatchField(data.match_field)
    except ValueError:
        raise ValidationError(
            f"Invalid match_field: {data.match_field}. "
            f"Must be one of: {', '.join(f.value for f in MatchField)}"
        )
    try:
        match_type = MatchType(data.match_type)
    except ValueError:
        raise ValidationError(
            f"Invalid match_type: {data.match_type}. "
            f"Must be one of: {', '.join(t.value for t in MatchType)}"
        )

    # If regex, validate the pattern compiles
    if match_type == MatchType.REGEX:
        try:
            re.compile(data.match_value)
        except re.error as e:
            raise ValidationError(f"Invalid regex pattern: {e}")

    rule = CategorizationRule(
        name=data.name,
        match_field=match_field,
        match_type=match_type,
        match_value=data.match_value,
        assign_category_id=data.assign_category_id,
        priority=data.priority,
        is_active=data.is_active,
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(
    db: AsyncSession, rule_id: uuid.UUID, data: CategorizationRuleUpdate
) -> CategorizationRule:
    """Update an existing categorization rule."""
    rule = await get_rule(db, rule_id)

    if data.name is not None:
        rule.name = data.name
    if data.match_field is not None:
        try:
            rule.match_field = MatchField(data.match_field)
        except ValueError:
            raise ValidationError(
                f"Invalid match_field: {data.match_field}. "
                f"Must be one of: {', '.join(f.value for f in MatchField)}"
            )
    if data.match_type is not None:
        try:
            rule.match_type = MatchType(data.match_type)
        except ValueError:
            raise ValidationError(
                f"Invalid match_type: {data.match_type}. "
                f"Must be one of: {', '.join(t.value for t in MatchType)}"
            )
    if data.match_value is not None:
        # Validate regex if applicable
        current_type = rule.match_type
        if current_type == MatchType.REGEX:
            try:
                re.compile(data.match_value)
            except re.error as e:
                raise ValidationError(f"Invalid regex pattern: {e}")
        rule.match_value = data.match_value
    if data.assign_category_id is not None:
        rule.assign_category_id = data.assign_category_id
    if data.priority is not None:
        rule.priority = data.priority
    if data.is_active is not None:
        rule.is_active = data.is_active

    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> None:
    """Delete a categorization rule."""
    rule = await get_rule(db, rule_id)
    await db.delete(rule)
    await db.commit()


# ---------------------------------------------------------------------------
# Rule matching logic
# ---------------------------------------------------------------------------


def _matches(rule: CategorizationRule, value: str) -> bool:
    """Check whether a single rule matches the given field value."""
    if not value:
        return False
    value_lower = value.lower()
    match_lower = rule.match_value.lower()

    if rule.match_type == MatchType.CONTAINS:
        return match_lower in value_lower
    elif rule.match_type == MatchType.EXACT:
        return value_lower == match_lower
    elif rule.match_type == MatchType.STARTS_WITH:
        return value_lower.startswith(match_lower)
    elif rule.match_type == MatchType.REGEX:
        try:
            return bool(re.search(rule.match_value, value, re.IGNORECASE))
        except re.error:
            return False
    return False


def _get_field_value(txn: PlaidTransaction, field: MatchField) -> str:
    """Extract the appropriate field from a transaction for matching."""
    if field == MatchField.NAME:
        return txn.name or ""
    elif field == MatchField.MERCHANT_NAME:
        return txn.merchant_name or ""
    elif field == MatchField.CATEGORY:
        return txn.category or ""
    return ""


async def apply_rules_to_transaction(
    db: AsyncSession,
    txn: PlaidTransaction,
    rules: list[CategorizationRule],
    user: User,
) -> bool:
    """Apply categorization rules to a single transaction.

    Returns True if a rule matched and the transaction was categorized.
    """
    if txn.is_categorized:
        return False

    for rule in rules:
        if not rule.is_active:
            continue
        field_value = _get_field_value(txn, rule.match_field)
        if _matches(rule, field_value):
            # Create an expense entry for this transaction
            expense = Expense(
                user_id=user.id,
                vendor_name=txn.merchant_name or txn.name,
                description=txn.name,
                amount=txn.amount,
                currency="USD",
                date=txn.date,
                category_id=rule.assign_category_id,
            )
            db.add(expense)
            await db.flush()
            txn.matched_expense_id = expense.id
            txn.is_categorized = True
            return True

    return False


async def apply_rules_to_all(
    db: AsyncSession,
    user: User,
) -> int:
    """Apply all active rules to uncategorized transactions belonging to this user.

    Returns the number of transactions that were categorized.
    """
    # Fetch active rules sorted by priority desc
    rules_result = await db.execute(
        select(CategorizationRule)
        .where(CategorizationRule.is_active.is_(True))
        .order_by(
            CategorizationRule.priority.desc(),
            CategorizationRule.created_at.asc(),
        )
    )
    rules = list(rules_result.scalars().all())

    if not rules:
        return 0

    # Fetch uncategorized transactions for this user
    txn_result = await db.execute(
        select(PlaidTransaction)
        .join(
            PlaidConnection,
            PlaidTransaction.plaid_connection_id == PlaidConnection.id,
        )
        .where(
            PlaidConnection.user_id == user.id,
            PlaidTransaction.is_categorized.is_(False),
        )
    )
    transactions = list(txn_result.scalars().all())

    categorized_count = 0
    for txn in transactions:
        matched = await apply_rules_to_transaction(db, txn, rules, user)
        if matched:
            categorized_count += 1

    await db.commit()
    return categorized_count
