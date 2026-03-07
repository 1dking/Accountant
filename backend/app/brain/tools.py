"""Structured data tools — SQL query functions that Claude calls via tool use.

Each tool queries existing PostgreSQL tables and returns formatted results.
These handle structured data (invoices, contacts, cashbook, etc.).

NOTE: This is a single-org system.  Tool queries intentionally have NO
user-scoped filters so that O-Brain can see all data regardless of who
created or imported it.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.retrieval_service import search_brain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _serialize(rows: list) -> list[dict]:
    """Convert SQLAlchemy model instances to dicts."""
    results = []
    for row in rows:
        d = {}
        for col in row.__table__.columns:
            val = getattr(row, col.name, None)
            if isinstance(val, (datetime, date)):
                d[col.name] = val.isoformat()
            elif isinstance(val, uuid.UUID):
                d[col.name] = str(val)
            elif hasattr(val, 'value'):
                d[col.name] = val.value
            else:
                d[col.name] = val
        results.append(d)
    return results


def _enum_val(v) -> str:
    """Get string value whether v is an Enum member or plain string."""
    return v.value if hasattr(v, 'value') else str(v)


# ---------------------------------------------------------------------------
# Tool definitions (for Claude function calling)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "query_invoices",
        "description": "Query invoices from the database. Returns invoice records with amounts, dates, contacts, status. Use for financial questions about invoices, revenue, payments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "Filter by contact UUID"},
                "status": {"type": "string", "description": "Filter by status: draft, sent, viewed, paid, overdue, cancelled, partially_paid"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_cashbook",
        "description": "Query cashbook entries (income/expense transactions). Returns entries with amounts, categories, dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_type": {"type": "string", "description": "income or expense"},
                "category": {"type": "string", "description": "Category name to filter by"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_contacts",
        "description": "Query contacts (clients and vendors). Returns contact records with names, emails, companies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search in name, email, company"},
                "type": {"type": "string", "description": "client, vendor, or both"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_proposals",
        "description": "Query proposals. Returns proposals with values, statuses, contacts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "draft, sent, viewed, waiting_signature, signed, declined, paid"},
                "contact_id": {"type": "string", "description": "Filter by contact UUID"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_expenses",
        "description": "Query expense records. Returns expenses with amounts, vendors, categories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category name"},
                "vendor": {"type": "string", "description": "Vendor name search"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_revenue_summary",
        "description": "Get revenue summary — total income grouped by month or client. Use for revenue and financial overview questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "this_month, last_month, this_quarter, this_year, last_year"},
            },
        },
    },
    {
        "name": "query_overdue_items",
        "description": "Get all overdue invoices and unsigned proposals older than 7 days.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_calendar_bookings",
        "description": "Query upcoming and past calendar events and bookings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "search_communications",
        "description": "Semantic search across emails, SMS, and call notes. Use for questions about what was discussed, communicated, or agreed upon.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "contact_id": {"type": "string", "description": "Filter by contact UUID"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_meeting_transcripts",
        "description": "Semantic search across meeting and call transcriptions. Use for questions about what was said in meetings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "contact_id": {"type": "string", "description": "Filter by contact UUID"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_documents",
        "description": "Semantic search across uploaded Drive files and brand knowledge.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_brain",
        "description": "Broad semantic search across ALL unstructured content (emails, transcripts, documents, notes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default 15)"},
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def execute_tool(
    db: AsyncSession,
    user_id: uuid.UUID,
    tool_name: str,
    tool_input: dict,
) -> str:
    """Execute a tool and return the result as a JSON string."""
    handlers = {
        "query_invoices": _query_invoices,
        "query_cashbook": _query_cashbook,
        "query_contacts": _query_contacts,
        "query_proposals": _query_proposals,
        "query_expenses": _query_expenses,
        "query_revenue_summary": _query_revenue_summary,
        "query_overdue_items": _query_overdue_items,
        "query_calendar_bookings": _query_calendar_bookings,
        "search_communications": _search_communications,
        "search_meeting_transcripts": _search_meeting_transcripts,
        "search_documents": _search_documents,
        "search_brain": _search_brain_tool,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        return await handler(db, user_id, tool_input)
    except Exception as e:
        logger.exception("Tool %s failed with input %s", tool_name, tool_input)
        return json.dumps({"error": f"Tool '{tool_name}' failed: {str(e)[:300]}"})


# ---------------------------------------------------------------------------
# Structured data tool implementations
# ---------------------------------------------------------------------------

async def _query_invoices(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice

    conditions = []
    if params.get("contact_id"):
        conditions.append(Invoice.contact_id == uuid.UUID(params["contact_id"]))
    if params.get("status"):
        conditions.append(Invoice.status == params["status"])
    if params.get("date_from"):
        conditions.append(Invoice.issue_date >= params["date_from"])
    if params.get("date_to"):
        conditions.append(Invoice.issue_date <= params["date_to"])

    limit = min(params.get("limit", 20), 50)
    stmt = select(Invoice)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(Invoice.issue_date)).limit(limit)
    result = await db.execute(stmt)
    invoices = list(result.scalars().all())
    return json.dumps({"invoices": _serialize(invoices), "count": len(invoices)})


async def _query_cashbook(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.cashbook.models import CashbookEntry

    conditions = []
    if params.get("entry_type"):
        conditions.append(CashbookEntry.entry_type == params["entry_type"].lower())
    if params.get("date_from"):
        conditions.append(CashbookEntry.date >= params["date_from"])
    if params.get("date_to"):
        conditions.append(CashbookEntry.date <= params["date_to"])

    limit = min(params.get("limit", 20), 50)
    stmt = select(CashbookEntry)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(CashbookEntry.date)).limit(limit)
    result = await db.execute(stmt)
    entries = list(result.scalars().all())

    total_income = sum(float(e.total_amount) for e in entries if _enum_val(e.entry_type) == "income")
    total_expense = sum(float(e.total_amount) for e in entries if _enum_val(e.entry_type) == "expense")

    return json.dumps({
        "entries": _serialize(entries),
        "count": len(entries),
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net": float(total_income - total_expense),
    })


async def _query_contacts(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.contacts.models import Contact

    conditions = [Contact.is_active == True]  # noqa: E712
    if params.get("search"):
        q = f"%{params['search']}%"
        conditions.append(
            or_(
                Contact.company_name.ilike(q),
                Contact.contact_name.ilike(q),
                Contact.email.ilike(q),
            )
        )
    if params.get("type"):
        conditions.append(Contact.type == params["type"].lower())

    limit = min(params.get("limit", 20), 50)
    stmt = select(Contact).where(and_(*conditions)).limit(limit)
    result = await db.execute(stmt)
    contacts = list(result.scalars().all())
    return json.dumps({"contacts": _serialize(contacts), "count": len(contacts)})


async def _query_proposals(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.proposals.models import Proposal

    conditions = []
    if params.get("status"):
        conditions.append(Proposal.status == params["status"])
    if params.get("contact_id"):
        conditions.append(Proposal.contact_id == uuid.UUID(params["contact_id"]))

    limit = min(params.get("limit", 20), 50)
    stmt = select(Proposal)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(Proposal.created_at)).limit(limit)
    result = await db.execute(stmt)
    proposals = list(result.scalars().all())

    total_value = sum(float(p.value or 0) for p in proposals)
    return json.dumps({
        "proposals": _serialize(proposals),
        "count": len(proposals),
        "total_value": float(total_value),
    })


async def _query_expenses(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.accounting.models import Expense

    conditions = []
    if params.get("vendor"):
        conditions.append(Expense.vendor_name.ilike(f"%{params['vendor']}%"))
    if params.get("date_from"):
        conditions.append(Expense.date >= params["date_from"])
    if params.get("date_to"):
        conditions.append(Expense.date <= params["date_to"])

    limit = min(params.get("limit", 20), 50)
    stmt = select(Expense)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(Expense.date)).limit(limit)
    result = await db.execute(stmt)
    expenses = list(result.scalars().all())

    total = sum(e.amount for e in expenses)
    return json.dumps({"expenses": _serialize(expenses), "count": len(expenses), "total": float(total)})


async def _query_revenue_summary(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice
    from app.income.models import Income

    period = params.get("period", "this_month")
    today = date.today()

    if period == "this_month":
        start = today.replace(day=1)
        end = today
    elif period == "last_month":
        first = today.replace(day=1)
        end = first - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "this_quarter":
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        end = today
    elif period == "this_year":
        start = date(today.year, 1, 1)
        end = today
    else:
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)

    # Paid invoices in period
    stmt = select(Invoice).where(
        and_(
            Invoice.status == "paid",
            Invoice.issue_date >= start.isoformat(),
            Invoice.issue_date <= end.isoformat(),
        )
    )
    result = await db.execute(stmt)
    paid_invoices = list(result.scalars().all())
    invoice_revenue = sum(float(i.total) for i in paid_invoices)

    # Income records in period
    stmt2 = select(Income).where(
        and_(
            Income.date >= start.isoformat(),
            Income.date <= end.isoformat(),
        )
    )
    result2 = await db.execute(stmt2)
    incomes = list(result2.scalars().all())
    income_total = sum(float(i.amount) for i in incomes)

    return json.dumps({
        "period": period,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "invoice_revenue": float(invoice_revenue),
        "other_income": float(income_total),
        "total_revenue": float(invoice_revenue + income_total),
        "paid_invoice_count": len(paid_invoices),
    })


async def _query_overdue_items(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice
    from app.proposals.models import Proposal

    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    # Overdue invoices
    stmt = select(Invoice).where(
        Invoice.status == "overdue"
    ).order_by(Invoice.due_date)
    result = await db.execute(stmt)
    overdue_invoices = list(result.scalars().all())

    # Unsigned proposals > 7 days
    stmt2 = select(Proposal).where(
        and_(
            Proposal.status.in_(["sent", "viewed", "waiting_signature"]),
            Proposal.sent_at <= datetime.combine(seven_days_ago, datetime.min.time()),
        )
    )
    result2 = await db.execute(stmt2)
    stale_proposals = list(result2.scalars().all())

    return json.dumps({
        "overdue_invoices": _serialize(overdue_invoices),
        "overdue_invoice_count": len(overdue_invoices),
        "overdue_total": float(sum(float(i.total) for i in overdue_invoices)),
        "stale_proposals": _serialize(stale_proposals),
        "stale_proposal_count": len(stale_proposals),
    })


async def _query_calendar_bookings(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.calendar.models import CalendarEvent

    today = date.today()
    date_from = params.get("date_from", today.isoformat())
    date_to = params.get("date_to", (today + timedelta(days=30)).isoformat())

    conditions = [
        CalendarEvent.date >= date_from,
        CalendarEvent.date <= date_to,
    ]

    limit = min(params.get("limit", 10), 30)
    stmt = select(CalendarEvent).where(and_(*conditions)).order_by(CalendarEvent.date).limit(limit)
    result = await db.execute(stmt)
    events = list(result.scalars().all())
    return json.dumps({"events": _serialize(events), "count": len(events)})


# ---------------------------------------------------------------------------
# Unstructured search tool implementations
# ---------------------------------------------------------------------------

async def _search_communications(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    results = await search_brain(
        db, user_id, params["query"],
        source_types=["email", "sms", "call_notes"],
        contact_id=uuid.UUID(params["contact_id"]) if params.get("contact_id") else None,
        limit=params.get("limit", 10),
    )
    return json.dumps({"results": [
        {"content": r.content, "source_type": r.source_type, "relevance": r.relevance_score}
        for r in results
    ], "count": len(results)})


async def _search_meeting_transcripts(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    results = await search_brain(
        db, user_id, params["query"],
        source_types=["meeting_transcript", "call_transcript", "meeting_notes"],
        contact_id=uuid.UUID(params["contact_id"]) if params.get("contact_id") else None,
        limit=params.get("limit", 10),
    )
    return json.dumps({"results": [
        {"content": r.content, "source_type": r.source_type, "relevance": r.relevance_score}
        for r in results
    ], "count": len(results)})


async def _search_documents(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    results = await search_brain(
        db, user_id, params["query"],
        source_types=["document", "brand_knowledge"],
        limit=params.get("limit", 10),
    )
    return json.dumps({"results": [
        {"content": r.content, "source_type": r.source_type, "relevance": r.relevance_score}
        for r in results
    ], "count": len(results)})


async def _search_brain_tool(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    results = await search_brain(
        db, user_id, params["query"],
        limit=params.get("limit", 15),
    )
    return json.dumps({"results": [
        {"content": r.content, "source_type": r.source_type, "relevance": r.relevance_score}
        for r in results
    ], "count": len(results)})
