"""Business logic for the accounting module."""


from typing import Optional

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounting.models import (
    ApprovalStatusEnum,
    Expense,
    ExpenseApproval,
    ExpenseCategory,
    ExpenseLineItem,
    ExpenseStatus,
)
from app.accounting.schemas import (
    CategorySpend,
    ExpenseCreate,
    ExpenseFilter,
    ExpenseLineItemCreate,
    ExpenseUpdate,
    MonthlySpend,
    VendorSpend,
)
from app.auth.models import User
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.documents.models import Document

# ---------------------------------------------------------------------------
# Default expense categories
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES = [
    {"name": "Food & Dining", "color": "#ef4444", "icon": "utensils"},
    {"name": "Transportation", "color": "#f97316", "icon": "car"},
    {"name": "Office Supplies", "color": "#eab308", "icon": "paperclip"},
    {"name": "Travel", "color": "#22c55e", "icon": "plane"},
    {"name": "Utilities", "color": "#06b6d4", "icon": "zap"},
    {"name": "Insurance", "color": "#3b82f6", "icon": "shield"},
    {"name": "Professional Services", "color": "#6366f1", "icon": "briefcase"},
    {"name": "Software & Subscriptions", "color": "#8b5cf6", "icon": "monitor"},
    {"name": "Marketing", "color": "#ec4899", "icon": "megaphone"},
    {"name": "Equipment", "color": "#14b8a6", "icon": "wrench"},
    {"name": "Taxes", "color": "#64748b", "icon": "landmark"},
    {"name": "Entertainment", "color": "#f43f5e", "icon": "music"},
    {"name": "Healthcare", "color": "#10b981", "icon": "heart-pulse"},
    {"name": "Education", "color": "#0ea5e9", "icon": "graduation-cap"},
    {"name": "Other", "color": "#6b7280", "icon": "circle-dot"},
]


async def seed_default_categories(db: AsyncSession) -> list[ExpenseCategory]:
    """Create built-in expense categories if they don't exist yet."""
    result = await db.execute(select(ExpenseCategory).where(ExpenseCategory.is_system))
    existing = {cat.name for cat in result.scalars().all()}

    created = []
    for cat_data in DEFAULT_CATEGORIES:
        if cat_data["name"] not in existing:
            cat = ExpenseCategory(
                name=cat_data["name"],
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_system=True,
            )
            db.add(cat)
            created.append(cat)

    if created:
        await db.commit()
        for cat in created:
            await db.refresh(cat)

    return created


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


async def list_categories(db: AsyncSession) -> list[ExpenseCategory]:
    result = await db.execute(select(ExpenseCategory).order_by(ExpenseCategory.name))
    return list(result.scalars().all())


async def create_category(
    db: AsyncSession,
    name: str,
    user: User,
    color: str | None = None,
    icon: str | None = None,
) -> ExpenseCategory:
    # Check for duplicate name
    result = await db.execute(select(ExpenseCategory).where(ExpenseCategory.name == name))
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"A category named '{name}' already exists.")

    category = ExpenseCategory(
        name=name,
        color=color,
        icon=icon,
        is_system=False,
        created_by=user.id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    name: str | None = None,
    color: str | None = None,
    icon: str | None = None,
) -> ExpenseCategory:
    result = await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == category_id))
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("ExpenseCategory", str(category_id))

    if name is not None:
        # Check for duplicate
        dup = await db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.name == name,
                ExpenseCategory.id != category_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(f"A category named '{name}' already exists.")
        category.name = name

    if color is not None:
        category.color = color
    if icon is not None:
        category.icon = icon

    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    result = await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == category_id))
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("ExpenseCategory", str(category_id))
    if category.is_system:
        raise ForbiddenError("Cannot delete a system category.")

    await db.delete(category)
    await db.commit()


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------


async def create_expense(
    db: AsyncSession,
    data: ExpenseCreate,
    user: User,
) -> Expense:
    # Ensure the accounting period is open
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, data.date)

    expense = Expense(
        document_id=data.document_id,
        category_id=data.category_id,
        user_id=user.id,
        vendor_name=data.vendor_name,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        tax_amount=data.tax_amount,
        date=data.date,
        payment_method=data.payment_method,
        status=ExpenseStatus.DRAFT,
        notes=data.notes,
        is_recurring=data.is_recurring,
    )
    db.add(expense)
    await db.flush()

    # Create line items
    for item_data in data.line_items:
        item = ExpenseLineItem(
            expense_id=expense.id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total=item_data.total,
        )
        db.add(item)

    await db.commit()
    await db.refresh(expense)
    return expense


async def create_expense_from_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    user: User,
) -> Expense:
    """Create an expense pre-filled from a document's AI-extracted metadata."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document", str(document_id))

    meta = document.extracted_metadata
    if not meta:
        raise ValidationError("This document has no extracted metadata. Run AI extraction first.")

    # Map the AI-suggested category to a real category
    category_id = None
    ai_category = meta.get("category")
    if ai_category:
        # Try to find a matching category by mapping AI category names
        ai_to_category_name = {
            "food_dining": "Food & Dining",
            "transportation": "Transportation",
            "office_supplies": "Office Supplies",
            "travel": "Travel",
            "utilities": "Utilities",
            "insurance": "Insurance",
            "professional_services": "Professional Services",
            "software_subscriptions": "Software & Subscriptions",
            "marketing": "Marketing",
            "equipment": "Equipment",
            "taxes": "Taxes",
            "entertainment": "Entertainment",
            "healthcare": "Healthcare",
            "education": "Education",
            "other": "Other",
        }
        category_name = ai_to_category_name.get(ai_category)
        if category_name:
            cat_result = await db.execute(
                select(ExpenseCategory).where(ExpenseCategory.name == category_name)
            )
            cat = cat_result.scalar_one_or_none()
            if cat:
                category_id = cat.id

    # Parse payment method
    payment_method = None
    pm_raw = meta.get("payment_method")
    if pm_raw:
        try:
            from app.accounting.models import PaymentMethod

            payment_method = PaymentMethod(pm_raw)
        except ValueError:
            pass

    # Parse date
    expense_date = date.today()
    date_str = meta.get("date")
    if date_str:
        try:
            expense_date = date.fromisoformat(date_str)
        except ValueError:
            pass

    expense = Expense(
        document_id=document_id,
        category_id=category_id,
        user_id=user.id,
        vendor_name=meta.get("vendor_name"),
        description=f"Expense from {document.title or document.original_filename}",
        amount=meta.get("total_amount") or 0.0,
        currency=meta.get("currency", "USD"),
        tax_amount=meta.get("tax_amount"),
        date=expense_date,
        payment_method=payment_method,
        status=ExpenseStatus.DRAFT,
        ai_category_suggestion=ai_category,
    )
    db.add(expense)
    await db.flush()

    # Create line items from extracted data
    for item_data in meta.get("line_items", []):
        if isinstance(item_data, dict) and item_data.get("description"):
            item = ExpenseLineItem(
                expense_id=expense.id,
                description=item_data["description"],
                quantity=item_data.get("quantity"),
                unit_price=item_data.get("unit_price"),
                total=item_data.get("total") or 0.0,
            )
            db.add(item)

    await db.commit()
    await db.refresh(expense)
    return expense


async def list_expenses(
    db: AsyncSession,
    filters: ExpenseFilter,
    pagination: PaginationParams,
) -> tuple[list[Expense], dict]:
    query = select(Expense).options(
        selectinload(Expense.category),
        selectinload(Expense.line_items),
    )

    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(
            or_(
                Expense.vendor_name.ilike(search_term),
                Expense.description.ilike(search_term),
            )
        )

    if filters.category_id is not None:
        query = query.where(Expense.category_id == filters.category_id)
    if filters.status is not None:
        query = query.where(Expense.status == filters.status)
    if filters.payment_method is not None:
        query = query.where(Expense.payment_method == filters.payment_method)
    if filters.date_from is not None:
        query = query.where(Expense.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Expense.date <= filters.date_to)
    if filters.min_amount is not None:
        query = query.where(Expense.amount >= filters.min_amount)
    if filters.max_amount is not None:
        query = query.where(Expense.amount <= filters.max_amount)
    if filters.user_id is not None:
        query = query.where(Expense.user_id == filters.user_id)

    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    query = query.order_by(Expense.date.desc(), Expense.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await db.execute(query)
    expenses = list(result.scalars().unique().all())

    meta = build_pagination_meta(total_count, pagination)
    return expenses, meta


async def get_expense(db: AsyncSession, expense_id: uuid.UUID) -> Expense:
    result = await db.execute(
        select(Expense)
        .options(
            selectinload(Expense.category),
            selectinload(Expense.line_items),
        )
        .where(Expense.id == expense_id)
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise NotFoundError("Expense", str(expense_id))
    return expense


async def update_expense(
    db: AsyncSession,
    expense_id: uuid.UUID,
    updates: ExpenseUpdate,
    user: User,
) -> Expense:
    expense = await get_expense(db, expense_id)

    # Check the current expense date's period and the new date's period (if changing)
    from app.accounting.period_service import assert_period_open

    await assert_period_open(db, expense.date)
    if updates.date is not None and updates.date != expense.date:
        await assert_period_open(db, updates.date)

    update_data = updates.model_dump(exclude_unset=True)

    # Handle line items separately
    new_line_items = update_data.pop("line_items", None)

    for field, value in update_data.items():
        setattr(expense, field, value)

    # Replace line items if provided
    if new_line_items is not None:
        # Delete existing
        await db.execute(delete(ExpenseLineItem).where(ExpenseLineItem.expense_id == expense_id))
        # Create new
        for item_data in new_line_items:
            if isinstance(item_data, ExpenseLineItemCreate):
                item_data = item_data.model_dump()
            item = ExpenseLineItem(
                expense_id=expense_id,
                description=item_data["description"],
                quantity=item_data.get("quantity"),
                unit_price=item_data.get("unit_price"),
                total=item_data["total"],
            )
            db.add(item)

    await db.commit()
    await db.refresh(expense)
    return expense


async def delete_expense(db: AsyncSession, expense_id: uuid.UUID) -> None:
    expense = await get_expense(db, expense_id)
    await db.delete(expense)
    await db.commit()


# ---------------------------------------------------------------------------
# Summary / Aggregation queries
# ---------------------------------------------------------------------------


async def get_spending_by_category(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[CategorySpend]:
    query = (
        select(
            Expense.category_id,
            ExpenseCategory.name.label("category_name"),
            ExpenseCategory.color.label("category_color"),
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .group_by(Expense.category_id, ExpenseCategory.name, ExpenseCategory.color)
    )

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    if date_from is not None:
        query = query.where(Expense.date >= date_from)
    if date_to is not None:
        query = query.where(Expense.date <= date_to)

    query = query.order_by(func.sum(Expense.amount).desc())
    result = await db.execute(query)

    return [
        CategorySpend(
            category_id=row.category_id,
            category_name=row.category_name or "Uncategorized",
            category_color=row.category_color,
            total=float(row.total or 0),
            count=row.count,
        )
        for row in result.all()
    ]


async def get_spending_by_month(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    year: int | None = None,
) -> list[MonthlySpend]:
    query = select(
        extract("year", Expense.date).label("year"),
        extract("month", Expense.date).label("month"),
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
    ).group_by(
        extract("year", Expense.date),
        extract("month", Expense.date),
    )

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    if year is not None:
        query = query.where(extract("year", Expense.date) == year)

    query = query.order_by(
        extract("year", Expense.date),
        extract("month", Expense.date),
    )
    result = await db.execute(query)

    return [
        MonthlySpend(
            year=int(row.year),
            month=int(row.month),
            total=float(row.total or 0),
            count=row.count,
        )
        for row in result.all()
    ]


async def get_spending_by_vendor(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 10,
) -> list[VendorSpend]:
    query = (
        select(
            Expense.vendor_name,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(Expense.vendor_name.isnot(None))
        .group_by(Expense.vendor_name)
    )

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    if date_from is not None:
        query = query.where(Expense.date >= date_from)
    if date_to is not None:
        query = query.where(Expense.date <= date_to)

    query = query.order_by(func.sum(Expense.amount).desc()).limit(limit)
    result = await db.execute(query)

    return [
        VendorSpend(
            vendor_name=row.vendor_name or "Unknown",
            total=float(row.total or 0),
            count=row.count,
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Expense Approvals
# ---------------------------------------------------------------------------


async def request_expense_approval(
    db: AsyncSession,
    expense_id: uuid.UUID,
    requested_by: uuid.UUID,
    assigned_to: uuid.UUID,
) -> ExpenseApproval:
    """Request approval for an expense."""
    from app.core.websocket import websocket_manager
    from app.notifications.service import create_notification

    # Validate expense exists
    expense = await get_expense(db, expense_id)

    # Validate assigned user exists
    user_result = await db.execute(select(User).where(User.id == assigned_to))
    if user_result.scalar_one_or_none() is None:
        raise NotFoundError("User", str(assigned_to))

    # Check for existing pending approval
    existing = await db.execute(
        select(ExpenseApproval).where(
            ExpenseApproval.expense_id == expense_id,
            ExpenseApproval.status == ApprovalStatusEnum.PENDING,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValidationError("There is already a pending approval for this expense.")

    approval = ExpenseApproval(
        expense_id=expense_id,
        requested_by=requested_by,
        assigned_to=assigned_to,
    )
    db.add(approval)

    # Update expense status
    expense.status = ExpenseStatus.PENDING_REVIEW
    await db.commit()
    await db.refresh(approval)

    # Notify the assigned reviewer
    await create_notification(
        db,
        user_id=assigned_to,
        type="expense_approval_request",
        title="Expense approval requested",
        message=f"You have been asked to review an expense of {expense.amount} {expense.currency}.",
        resource_type="expense",
        resource_id=str(expense_id),
    )

    await websocket_manager.broadcast(
        {
            "event": "expense_approval_requested",
            "data": {
                "approval_id": str(approval.id),
                "expense_id": str(expense_id),
                "requested_by": str(requested_by),
                "assigned_to": str(assigned_to),
            },
        }
    )

    return approval


async def resolve_expense_approval(
    db: AsyncSession,
    expense_id: uuid.UUID,
    resolver_id: uuid.UUID,
    approve: bool,
    comment: str | None = None,
    is_admin: bool = False,
) -> ExpenseApproval:
    """Approve or reject an expense."""
    from app.core.websocket import websocket_manager
    from app.notifications.service import create_notification

    # Find the pending approval for this expense
    result = await db.execute(
        select(ExpenseApproval).where(
            ExpenseApproval.expense_id == expense_id,
            ExpenseApproval.status == ApprovalStatusEnum.PENDING,
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise NotFoundError("ExpenseApproval", str(expense_id))

    if approval.assigned_to != resolver_id and not is_admin:
        raise ForbiddenError("Only the assigned reviewer can resolve this approval.")

    new_status = ApprovalStatusEnum.APPROVED if approve else ApprovalStatusEnum.REJECTED
    approval.status = new_status
    approval.comment = comment
    approval.resolved_at = datetime.now(timezone.utc)

    # Update expense status
    expense = await get_expense(db, expense_id)
    expense.status = ExpenseStatus.APPROVED if approve else ExpenseStatus.REJECTED

    await db.commit()
    await db.refresh(approval)

    # Notify the requester
    status_text = "approved" if approve else "rejected"
    await create_notification(
        db,
        user_id=approval.requested_by,
        type="expense_approval_resolved",
        title=f"Expense {status_text}",
        message=f"Your expense approval request has been {status_text}.",
        resource_type="expense",
        resource_id=str(expense_id),
    )

    await websocket_manager.broadcast(
        {
            "event": "expense_approval_resolved",
            "data": {
                "approval_id": str(approval.id),
                "expense_id": str(expense_id),
                "status": new_status.value,
                "resolved_by": str(resolver_id),
            },
        }
    )

    return approval


async def get_expense_approval(
    db: AsyncSession,
    expense_id: uuid.UUID,
) -> ExpenseApproval | None:
    """Get the most recent approval for an expense."""
    result = await db.execute(
        select(ExpenseApproval)
        .where(ExpenseApproval.expense_id == expense_id)
        .order_by(ExpenseApproval.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_pending_expense_approvals(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[ExpenseApproval]:
    """List pending expense approvals assigned to a user."""
    result = await db.execute(
        select(ExpenseApproval)
        .where(
            ExpenseApproval.assigned_to == user_id,
            ExpenseApproval.status == ApprovalStatusEnum.PENDING,
        )
        .order_by(ExpenseApproval.created_at.desc())
    )
    return list(result.scalars().all())
