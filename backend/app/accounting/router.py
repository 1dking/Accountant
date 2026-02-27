"""FastAPI router for the accounting module."""


import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting import service
from app.accounting.export import export_expenses_csv, export_expenses_xlsx
from app.accounting.models import ExpenseStatus, PaymentMethod
from app.accounting.schemas import (
    ExpenseApprovalRequest,
    ExpenseApprovalResolve,
    ExpenseApprovalResponse,
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseFilter,
    ExpenseListItem,
    ExpenseResponse,
    ExpenseSummary,
    ExpenseUpdate,
)
from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.dependencies import get_current_user, get_db, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Category endpoints
# ---------------------------------------------------------------------------


@router.get("/categories")
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return all expense categories. Seeds defaults if none exist."""
    categories = await service.list_categories(db)
    if not categories:
        await service.seed_default_categories(db)
        categories = await service.list_categories(db)
    return {"data": [ExpenseCategoryResponse.model_validate(c) for c in categories]}


@router.post("/categories", status_code=201)
async def create_category(
    data: ExpenseCategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    category = await service.create_category(
        db, name=data.name, user=current_user, color=data.color, icon=data.icon
    )
    return {"data": ExpenseCategoryResponse.model_validate(category)}


@router.put("/categories/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    data: ExpenseCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    update_data = data.model_dump(exclude_unset=True)
    category = await service.update_category(db, category_id, **update_data)
    return {"data": ExpenseCategoryResponse.model_validate(category)}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_category(db, category_id)
    return {"data": {"message": "Category deleted successfully"}}


# ---------------------------------------------------------------------------
# Expense endpoints
# ---------------------------------------------------------------------------


@router.get("/expenses")
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    status: ExpenseStatus | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    user_id: uuid.UUID | None = None,
) -> dict:
    filters = ExpenseFilter(
        search=search,
        category_id=category_id,
        status=status,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        user_id=user_id,
    )
    expenses, meta = await service.list_expenses(db, filters, pagination)
    return {
        "data": [ExpenseListItem.model_validate(e) for e in expenses],
        "meta": meta,
    }


@router.post("/expenses", status_code=201)
async def create_expense(
    data: ExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    expense = await service.create_expense(db, data, current_user)
    return {"data": ExpenseResponse.model_validate(expense)}


@router.post("/expenses/from-document/{document_id}", status_code=201)
async def create_expense_from_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create an expense pre-filled from a document's AI-extracted metadata."""
    expense = await service.create_expense_from_document(db, document_id, current_user)
    return {"data": ExpenseResponse.model_validate(expense)}


@router.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    expense = await service.get_expense(db, expense_id)
    return {"data": ExpenseResponse.model_validate(expense)}


@router.put("/expenses/{expense_id}")
async def update_expense(
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    expense = await service.update_expense(db, expense_id, data, current_user)
    return {"data": ExpenseResponse.model_validate(expense)}


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    await service.delete_expense(db, expense_id)
    return {"data": {"message": "Expense deleted successfully"}}


# ---------------------------------------------------------------------------
# Summary / Analytics endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: uuid.UUID | None = None,
    year: int | None = None,
) -> dict:
    by_category = await service.get_spending_by_category(db, user_id, date_from, date_to)
    by_month = await service.get_spending_by_month(db, user_id, year)
    top_vendors = await service.get_spending_by_vendor(db, user_id, date_from, date_to)

    total_amount = sum(c.total for c in by_category)
    expense_count = sum(c.count for c in by_category)
    average_amount = total_amount / expense_count if expense_count > 0 else 0.0

    return {
        "data": ExpenseSummary(
            total_amount=total_amount,
            expense_count=expense_count,
            average_amount=round(average_amount, 2),
            by_category=by_category,
            by_month=by_month,
            top_vendors=top_vendors,
        ).model_dump(mode="json")
    }


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.get("/export/csv")
async def export_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    status: ExpenseStatus | None = None,
) -> Response:
    """Export filtered expenses as a CSV file."""
    filters = ExpenseFilter(
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        status=status,
    )
    csv_bytes = await export_expenses_csv(db, filters)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
    )


@router.get("/export/xlsx")
async def export_xlsx(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    status: ExpenseStatus | None = None,
) -> Response:
    """Export filtered expenses as an XLSX file."""
    filters = ExpenseFilter(
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        status=status,
    )
    xlsx_bytes = await export_expenses_xlsx(db, filters)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="expenses.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Expense Approval endpoints
# ---------------------------------------------------------------------------


@router.get("/expenses/pending-approvals")
async def list_pending_approvals(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return expense approvals assigned to the current user that are still pending."""
    approvals = await service.list_pending_expense_approvals(db, current_user.id)
    return {"data": [ExpenseApprovalResponse.model_validate(a) for a in approvals]}


@router.get("/expenses/{expense_id}/approval")
async def get_expense_approval(
    expense_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get the latest approval for an expense."""
    approval = await service.get_expense_approval(db, expense_id)
    return {
        "data": ExpenseApprovalResponse.model_validate(approval) if approval else None,
    }


@router.post("/expenses/{expense_id}/request-approval", status_code=201)
async def request_approval(
    expense_id: uuid.UUID,
    data: ExpenseApprovalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    approval = await service.request_expense_approval(
        db,
        expense_id=expense_id,
        requested_by=current_user.id,
        assigned_to=data.assigned_to,
    )
    return {"data": ExpenseApprovalResponse.model_validate(approval)}


@router.post("/expenses/{expense_id}/approve")
async def approve_expense(
    expense_id: uuid.UUID,
    data: ExpenseApprovalResolve,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    approval = await service.resolve_expense_approval(
        db,
        expense_id=expense_id,
        resolver_id=current_user.id,
        approve=True,
        comment=data.comment,
    )
    return {"data": ExpenseApprovalResponse.model_validate(approval)}


@router.post("/expenses/{expense_id}/reject")
async def reject_expense(
    expense_id: uuid.UUID,
    data: ExpenseApprovalResolve,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    approval = await service.resolve_expense_approval(
        db,
        expense_id=expense_id,
        resolver_id=current_user.id,
        approve=False,
        comment=data.comment,
    )
    return {"data": ExpenseApprovalResponse.model_validate(approval)}
