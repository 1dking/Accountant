"""Structured data tools — SQL query functions that Claude calls via tool use.

Each tool queries existing PostgreSQL tables and returns formatted results.
These handle structured data (invoices, contacts, cashbook, etc.).

NOTE: This is a single-org system.  Tool queries intentionally have NO
user-scoped filters so that O-Brain can see all data regardless of who
created or imported it.

IMPORTANT: PostgreSQL stores enum values as UPPERCASE member names
(e.g. INCOME, EXPENSE, PAID, CLIENT).  All comparisons must use .upper().
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.retrieval_service import search_brain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
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
            elif isinstance(val, Decimal):
                d[col.name] = float(val)
            elif hasattr(val, 'value'):
                d[col.name] = val.value
            else:
                d[col.name] = val
        results.append(d)
    return results


def _enum_val(v) -> str:
    """Get the UPPERCASE string from an enum member or plain string."""
    if hasattr(v, 'name'):
        return v.name  # Python enum → NAME is uppercase
    if hasattr(v, 'value'):
        return str(v.value).upper()
    return str(v).upper()


async def _resolve_contact(db: AsyncSession, name_or_id: str):
    """Look up a contact by UUID or by name search. Returns Contact or None."""
    from app.contacts.models import Contact

    # Try UUID first
    try:
        cid = uuid.UUID(name_or_id)
        result = await db.execute(
            select(Contact).where(Contact.id == cid)
        )
        return result.scalar_one_or_none()
    except (ValueError, AttributeError):
        pass

    # Search by name
    q = f"%{name_or_id}%"
    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.is_active == True,  # noqa: E712
                or_(
                    Contact.company_name.ilike(q),
                    Contact.contact_name.ilike(q),
                ),
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_user(db: AsyncSession, user_id: uuid.UUID):
    """Fetch User object for write operations."""
    from app.auth.models import User
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _get_default_account(db: AsyncSession):
    """Get the first payment account (default)."""
    from app.cashbook.models import PaymentAccount
    result = await db.execute(select(PaymentAccount).limit(1))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# READ Tool definitions (for Claude function calling)
# ---------------------------------------------------------------------------

READ_TOOL_DEFINITIONS = [
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
        "description": "Query cashbook entries (income/expense transactions). Returns entries with amounts, categories, dates. This is the main ledger for all money in/out.",
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
        "description": "Query expense records from the expenses table AND expense-type cashbook entries. Returns expenses with amounts, vendors, categories, dates. Use for any question about spending.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Vendor name search"},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "query_revenue_summary",
        "description": "Get revenue summary — total income grouped by period. Use for revenue and financial overview questions.",
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
        "description": "Semantic search across emails, SMS, and call notes.",
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
        "description": "Semantic search across meeting and call transcriptions.",
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
# WRITE Tool definitions
# ---------------------------------------------------------------------------

PAGE_TOOL_DEFINITIONS = [
    {
        "name": "create_page",
        "description": "Create a new landing page using AI. O-Brain should confirm details with the user first (services, goal, brand colors, headline), then call this tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"},
                "prompt": {"type": "string", "description": "Detailed prompt describing the page to generate (include target audience, goal, services, etc.)"},
                "style_preset": {"type": "string", "description": "Style: modern, corporate, creative, startup, elegant, dark"},
                "primary_color": {"type": "string", "description": "Primary brand color hex (e.g. #2563eb)"},
                "font_family": {"type": "string", "description": "Font family (e.g. Inter, Montserrat)"},
            },
            "required": ["title", "prompt"],
        },
    },
    {
        "name": "create_website",
        "description": "Create a multi-page website. O-Brain should suggest page structure first, then call this after user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Website name"},
                "pages": {
                    "type": "array",
                    "description": "List of pages to create",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "slug": {"type": "string"},
                            "prompt": {"type": "string", "description": "What this page should contain"},
                            "is_homepage": {"type": "boolean"},
                        },
                        "required": ["title", "prompt"],
                    },
                },
                "style_preset": {"type": "string"},
                "primary_color": {"type": "string"},
            },
            "required": ["name", "pages"],
        },
    },
    {
        "name": "query_page_analytics",
        "description": "Get analytics for a specific page (visitors, sources, conversions, scroll depth, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_name": {"type": "string", "description": "Page title or slug to look up"},
                "days": {"type": "integer", "description": "Number of days to analyze (default 30)"},
            },
            "required": ["page_name"],
        },
    },
    {
        "name": "query_website_analytics",
        "description": "Get aggregate analytics for a multi-page website.",
        "input_schema": {
            "type": "object",
            "properties": {
                "website_name": {"type": "string", "description": "Website name or slug"},
                "days": {"type": "integer", "description": "Number of days (default 30)"},
            },
            "required": ["website_name"],
        },
    },
]

WRITE_TOOL_DEFINITIONS = [
    {
        "name": "create_expense",
        "description": "Create a new expense entry in the cashbook. Use when the user wants to record spending, add a bill, or log a purchase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Vendor/payee name (e.g. 'Canva', 'Staples')"},
                "amount": {"type": "number", "description": "Expense amount (positive number)"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"},
                "description": {"type": "string", "description": "Description of the expense"},
                "category": {"type": "string", "description": "Category name (e.g. 'Software & Subscriptions', 'Office Supplies')"},
            },
            "required": ["vendor", "amount"],
        },
    },
    {
        "name": "create_income_entry",
        "description": "Create a new income entry in the cashbook. Use when the user wants to record money received.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Income source name"},
                "amount": {"type": "number", "description": "Income amount (positive number)"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"},
                "description": {"type": "string", "description": "Description of the income"},
                "category": {"type": "string", "description": "Category: service, product, interest, refund, or other"},
            },
            "required": ["source", "amount"],
        },
    },
    {
        "name": "create_invoice",
        "description": "Create a new draft invoice for a contact. Use when the user wants to bill a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string", "description": "Contact name or UUID"},
                "items": {
                    "type": "array",
                    "description": "Line items: each has description, quantity, rate",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number", "description": "Default 1"},
                            "rate": {"type": "number", "description": "Unit price"},
                        },
                        "required": ["description", "rate"],
                    },
                },
                "due_days": {"type": "integer", "description": "Days until due (default 30)"},
                "notes": {"type": "string", "description": "Invoice notes"},
                "currency": {"type": "string", "description": "Currency code (default USD)"},
            },
            "required": ["contact", "items"],
        },
    },
    {
        "name": "create_contact",
        "description": "Create a new contact (client, vendor, or both).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Company or person name"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Phone number"},
                "company": {"type": "string", "description": "Company name (if person name is different)"},
                "type": {"type": "string", "description": "client, vendor, or both (default: client)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_contact",
        "description": "Update an existing contact's fields (email, phone, company, notes, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string", "description": "Contact name or UUID"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["contact"],
        },
    },
    {
        "name": "add_contact_note",
        "description": "Add an internal note to a contact's activity timeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string", "description": "Contact name or UUID"},
                "note": {"type": "string", "description": "The note text"},
            },
            "required": ["contact", "note"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event, reminder, or task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "event_type": {"type": "string", "description": "deadline, reminder, meeting, or custom (default: reminder)"},
                "description": {"type": "string", "description": "Event description"},
            },
            "required": ["title", "date"],
        },
    },
    {
        "name": "create_proposal",
        "description": "Create a draft proposal for a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string", "description": "Contact name or UUID"},
                "title": {"type": "string", "description": "Proposal title"},
                "value": {"type": "number", "description": "Proposal value/amount"},
                "description": {"type": "string", "description": "Proposal description text"},
                "currency": {"type": "string", "description": "Currency code (default USD)"},
            },
            "required": ["contact", "title", "value"],
        },
    },
    {
        "name": "update_invoice_status",
        "description": "Update an invoice's status (e.g. mark as sent, paid, cancelled).",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice": {"type": "string", "description": "Invoice number (e.g. INV-0001) or UUID"},
                "status": {"type": "string", "description": "New status: draft, sent, paid, overdue, cancelled"},
            },
            "required": ["invoice", "status"],
        },
    },
    {
        "name": "create_booking",
        "description": "Create a booking/appointment on a scheduling calendar. Use when someone wants to book a meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "guest_name": {"type": "string", "description": "Guest's full name"},
                "guest_email": {"type": "string", "description": "Guest's email address"},
                "start_time": {"type": "string", "description": "Start time in ISO format (e.g. 2025-01-15T10:00:00)"},
                "meeting_type": {"type": "string", "description": "phone, video, or in_person (default: video)"},
                "guest_phone": {"type": "string", "description": "Guest's phone number"},
                "guest_notes": {"type": "string", "description": "Notes about the meeting"},
                "meeting_location": {"type": "string", "description": "Meeting location or link"},
            },
            "required": ["guest_name", "guest_email", "start_time"],
        },
    },
]

# ---------------------------------------------------------------------------
# ACTION Tool definitions (require user confirmation before executing)
# ---------------------------------------------------------------------------

ACTION_TOOL_DEFINITIONS = [
    {
        "name": "send_email",
        "description": "Draft an email for the user to review before sending. This creates a DRAFT that the user must confirm — never claim the email was sent. Tell the user to review the preview below.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body in HTML format. Use <p>, <br>, <strong>, <ul>/<li> for formatting."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "send_sms",
        "description": "Draft an SMS message for the user to review before sending. This creates a DRAFT that the user must confirm — never claim the SMS was sent. Tell the user to review the preview below. Keep messages under 160 characters when possible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient phone number (E.164 format preferred, e.g. +15551234567)"},
                "message": {"type": "string", "description": "SMS message text (aim for ≤160 chars)"},
            },
            "required": ["to", "message"],
        },
    },
    {
        "name": "create_document",
        "description": "Create a document in the Docs editor. This creates a draft for the user to review before saving. Use for generating reports, letters, memos, proposals, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "content": {"type": "string", "description": "Document content in HTML format"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "save_to_drive",
        "description": "Save a file to the Drive. Creates a draft for the user to confirm. Use when the user wants to save generated content (text, notes, summaries) as a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename with extension (e.g. 'meeting-notes.txt', 'report.html')"},
                "content": {"type": "string", "description": "File content (plain text or HTML)"},
                "folder": {"type": "string", "description": "Folder name to save in (optional, saves to root if not specified)"},
            },
            "required": ["filename", "content"],
        },
    },
]

# Combined definitions
TOOL_DEFINITIONS = READ_TOOL_DEFINITIONS + WRITE_TOOL_DEFINITIONS + PAGE_TOOL_DEFINITIONS + ACTION_TOOL_DEFINITIONS


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
        # Read tools
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
        # Write tools
        "create_expense": _create_expense,
        "create_income_entry": _create_income_entry,
        "create_invoice": _create_invoice,
        "create_contact": _create_contact,
        "update_contact": _update_contact,
        "add_contact_note": _add_contact_note,
        "create_calendar_event": _create_calendar_event,
        "create_proposal": _create_proposal,
        "update_invoice_status": _update_invoice_status,
        "create_booking": _create_booking,
        # Page/website tools
        "create_page": _create_page,
        "create_website": _create_website,
        "query_page_analytics": _query_page_analytics,
        "query_website_analytics": _query_website_analytics,
        # Action tools (create drafts for user confirmation)
        "send_email": _draft_email,
        "send_sms": _draft_sms,
        "create_document": _draft_document,
        "save_to_drive": _draft_save_to_drive,
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
# READ: Structured data tool implementations
# ---------------------------------------------------------------------------

async def _query_invoices(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice

    conditions = []
    if params.get("contact_id"):
        conditions.append(Invoice.contact_id == uuid.UUID(params["contact_id"]))
    if params.get("status"):
        conditions.append(Invoice.status == params["status"].upper())
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
    logger.info("query_invoices: %d results (filters: %s)", len(invoices), params)
    return json.dumps({"invoices": _serialize(invoices), "count": len(invoices)})


async def _query_cashbook(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.cashbook.models import CashbookEntry

    conditions = []
    if params.get("entry_type"):
        conditions.append(CashbookEntry.entry_type == params["entry_type"].upper())
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

    total_income = sum(float(e.total_amount) for e in entries if _enum_val(e.entry_type) == "INCOME")
    total_expense = sum(float(e.total_amount) for e in entries if _enum_val(e.entry_type) == "EXPENSE")

    logger.info("query_cashbook: %d results (filters: %s)", len(entries), params)
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
        conditions.append(Contact.type == params["type"].upper())

    limit = min(params.get("limit", 20), 50)
    stmt = select(Contact).where(and_(*conditions)).limit(limit)
    result = await db.execute(stmt)
    contacts = list(result.scalars().all())
    logger.info("query_contacts: %d results (filters: %s)", len(contacts), params)
    return json.dumps({"contacts": _serialize(contacts), "count": len(contacts)})


async def _query_proposals(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.proposals.models import Proposal

    conditions = []
    if params.get("status"):
        conditions.append(Proposal.status == params["status"].upper())
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
    logger.info("query_proposals: %d results (filters: %s)", len(proposals), params)
    return json.dumps({
        "proposals": _serialize(proposals),
        "count": len(proposals),
        "total_value": float(total_value),
    })


async def _query_expenses(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Query BOTH the expenses table AND cashbook expense entries."""
    from app.accounting.models import Expense
    from app.cashbook.models import CashbookEntry

    combined = []

    # 1) Expenses table
    exp_conditions = []
    if params.get("vendor"):
        exp_conditions.append(Expense.vendor_name.ilike(f"%{params['vendor']}%"))
    if params.get("date_from"):
        exp_conditions.append(Expense.date >= params["date_from"])
    if params.get("date_to"):
        exp_conditions.append(Expense.date <= params["date_to"])

    stmt = select(Expense)
    if exp_conditions:
        stmt = stmt.where(and_(*exp_conditions))
    stmt = stmt.order_by(desc(Expense.date)).limit(50)
    result = await db.execute(stmt)
    expenses = list(result.scalars().all())

    for e in expenses:
        combined.append({
            "source": "expenses",
            "id": str(e.id),
            "vendor": e.vendor_name or "",
            "description": e.description or "",
            "amount": float(e.amount),
            "currency": e.currency or "USD",
            "date": e.date.isoformat() if e.date else None,
            "status": _enum_val(e.status) if e.status else None,
        })

    # 2) Cashbook expense entries
    cb_conditions = [CashbookEntry.entry_type == "EXPENSE"]
    if params.get("vendor"):
        cb_conditions.append(CashbookEntry.description.ilike(f"%{params['vendor']}%"))
    if params.get("date_from"):
        cb_conditions.append(CashbookEntry.date >= params["date_from"])
    if params.get("date_to"):
        cb_conditions.append(CashbookEntry.date <= params["date_to"])

    stmt2 = select(CashbookEntry).where(and_(*cb_conditions)).order_by(desc(CashbookEntry.date)).limit(50)
    result2 = await db.execute(stmt2)
    cb_entries = list(result2.scalars().all())

    for e in cb_entries:
        combined.append({
            "source": "cashbook",
            "id": str(e.id),
            "vendor": "",
            "description": e.description or "",
            "amount": float(e.total_amount),
            "currency": "USD",
            "date": e.date.isoformat() if e.date else None,
            "status": "recorded",
        })

    # Sort by date desc and limit
    combined.sort(key=lambda x: x.get("date") or "", reverse=True)
    limit = min(params.get("limit", 20), 50)
    combined = combined[:limit]

    total = sum(e["amount"] for e in combined)
    logger.info("query_expenses: %d results (%d from expenses, %d from cashbook)", len(combined), len(expenses), len(cb_entries))
    return json.dumps({"expenses": combined, "count": len(combined), "total": float(total)})


async def _query_revenue_summary(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice
    from app.income.models import Income
    from app.cashbook.models import CashbookEntry

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
            Invoice.status == "PAID",
            Invoice.issue_date >= start.isoformat(),
            Invoice.issue_date <= end.isoformat(),
        )
    )
    result = await db.execute(stmt)
    paid_invoices = list(result.scalars().all())
    invoice_revenue = sum(float(i.total) for i in paid_invoices)

    # Income entries in period
    stmt2 = select(Income).where(
        and_(
            Income.date >= start.isoformat(),
            Income.date <= end.isoformat(),
        )
    )
    result2 = await db.execute(stmt2)
    incomes = list(result2.scalars().all())
    income_total = sum(float(i.amount) for i in incomes)

    # Cashbook income entries in period
    stmt3 = select(CashbookEntry).where(
        and_(
            CashbookEntry.entry_type == "INCOME",
            CashbookEntry.date >= start.isoformat(),
            CashbookEntry.date <= end.isoformat(),
        )
    )
    result3 = await db.execute(stmt3)
    cb_incomes = list(result3.scalars().all())
    cb_income_total = sum(float(e.total_amount) for e in cb_incomes)

    total_revenue = invoice_revenue + income_total + cb_income_total
    logger.info("query_revenue_summary: period=%s, invoices=%d, income=%d, cashbook=%d",
                period, len(paid_invoices), len(incomes), len(cb_incomes))
    return json.dumps({
        "period": period,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "invoice_revenue": float(invoice_revenue),
        "other_income": float(income_total),
        "cashbook_income": float(cb_income_total),
        "total_revenue": float(total_revenue),
        "paid_invoice_count": len(paid_invoices),
    })


async def _query_overdue_items(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    from app.invoicing.models import Invoice
    from app.proposals.models import Proposal

    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    stmt = select(Invoice).where(
        Invoice.status == "OVERDUE"
    ).order_by(Invoice.due_date)
    result = await db.execute(stmt)
    overdue_invoices = list(result.scalars().all())

    stmt2 = select(Proposal).where(
        and_(
            Proposal.status.in_(["SENT", "VIEWED", "WAITING_SIGNATURE"]),
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
# READ: Unstructured search tool implementations
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


# ---------------------------------------------------------------------------
# WRITE: Tool implementations
# ---------------------------------------------------------------------------

async def _create_expense(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a cashbook expense entry."""
    from app.cashbook.models import CashbookEntry, EntryType

    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    account = await _get_default_account(db)
    if not account:
        return json.dumps({"error": "No payment account found. Please create one first in Cashbook settings."})

    expense_date = date.fromisoformat(params["date"]) if params.get("date") else date.today()
    amount = Decimal(str(params["amount"]))
    description = params.get("description") or f"Payment to {params['vendor']}"

    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=account.id,
        entry_type=EntryType.EXPENSE,
        date=expense_date,
        description=description,
        total_amount=amount,
        user_id=user_id,
        notes=f"Created by O-Brain. Vendor: {params['vendor']}",
    )
    db.add(entry)
    await db.commit()

    logger.info("Created expense: $%.2f to %s on %s", float(amount), params['vendor'], expense_date)
    return json.dumps({
        "success": True,
        "message": f"Expense created: ${float(amount):.2f} to {params['vendor']} on {expense_date.strftime('%b %d, %Y')}",
        "id": str(entry.id),
    })


async def _create_income_entry(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a cashbook income entry."""
    from app.cashbook.models import CashbookEntry, EntryType

    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    account = await _get_default_account(db)
    if not account:
        return json.dumps({"error": "No payment account found."})

    income_date = date.fromisoformat(params["date"]) if params.get("date") else date.today()
    amount = Decimal(str(params["amount"]))
    description = params.get("description") or f"Income from {params['source']}"

    entry = CashbookEntry(
        id=uuid.uuid4(),
        account_id=account.id,
        entry_type=EntryType.INCOME,
        date=income_date,
        description=description,
        total_amount=amount,
        user_id=user_id,
        notes=f"Created by O-Brain. Source: {params['source']}",
    )
    db.add(entry)
    await db.commit()

    logger.info("Created income: $%.2f from %s on %s", float(amount), params['source'], income_date)
    return json.dumps({
        "success": True,
        "message": f"Income recorded: ${float(amount):.2f} from {params['source']} on {income_date.strftime('%b %d, %Y')}",
        "id": str(entry.id),
    })


async def _create_invoice(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a draft invoice using the invoicing service."""
    from app.invoicing.service import create_invoice
    from app.invoicing.schemas import InvoiceCreate, InvoiceLineItemCreate

    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    contact = await _resolve_contact(db, params["contact"])
    if not contact:
        return json.dumps({"error": f"Contact '{params['contact']}' not found. Please create them first."})

    due_days = params.get("due_days", 30)
    items = params.get("items", [])
    if not items:
        return json.dumps({"error": "At least one line item is required."})

    line_items = [
        InvoiceLineItemCreate(
            description=item["description"],
            quantity=Decimal(str(item.get("quantity", 1))),
            unit_price=Decimal(str(item["rate"])),
        )
        for item in items
    ]

    data = InvoiceCreate(
        contact_id=contact.id,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=due_days),
        currency=params.get("currency", "USD"),
        notes=params.get("notes"),
        line_items=line_items,
    )

    invoice = await create_invoice(db, data, user)
    total = float(invoice.total)
    contact_name = contact.contact_name or contact.company_name

    logger.info("Created invoice %s for %s — $%.2f", invoice.invoice_number, contact_name, total)
    return json.dumps({
        "success": True,
        "message": f"Draft invoice {invoice.invoice_number} created for {contact_name} — ${total:.2f}. View at /invoices/{invoice.id}",
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
    })


async def _create_contact(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a new contact."""
    from app.contacts.service import create_contact
    from app.contacts.schemas import ContactCreate
    from app.contacts.models import ContactType

    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    contact_type_str = (params.get("type") or "client").upper()
    try:
        contact_type = ContactType[contact_type_str]
    except KeyError:
        contact_type = ContactType.CLIENT

    company = params.get("company") or params["name"]
    contact_name = params["name"] if params.get("company") else None

    data = ContactCreate(
        type=contact_type,
        company_name=company,
        contact_name=contact_name,
        email=params.get("email"),
        phone=params.get("phone"),
    )

    contact = await create_contact(db, data, user)
    display_name = contact.contact_name or contact.company_name
    email_part = f" ({contact.email})" if contact.email else ""

    logger.info("Created contact: %s%s", display_name, email_part)
    return json.dumps({
        "success": True,
        "message": f"Contact created: {display_name}{email_part}",
        "id": str(contact.id),
    })


async def _update_contact(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Update an existing contact."""
    contact = await _resolve_contact(db, params["contact"])
    if not contact:
        return json.dumps({"error": f"Contact '{params['contact']}' not found."})

    changes = []
    if params.get("email"):
        contact.email = params["email"]
        changes.append(f"email → {params['email']}")
    if params.get("phone"):
        contact.phone = params["phone"]
        changes.append(f"phone → {params['phone']}")
    if params.get("company"):
        contact.company_name = params["company"]
        changes.append(f"company → {params['company']}")
    if params.get("notes"):
        contact.notes = params["notes"]
        changes.append("notes updated")

    if not changes:
        return json.dumps({"message": "No changes specified."})

    await db.commit()
    display_name = contact.contact_name or contact.company_name
    return json.dumps({
        "success": True,
        "message": f"Updated {display_name}: {', '.join(changes)}",
    })


async def _add_contact_note(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Add a note to a contact's activity timeline."""
    from app.contacts.service import log_contact_activity
    from app.contacts.models import ActivityType

    contact = await _resolve_contact(db, params["contact"])
    if not contact:
        return json.dumps({"error": f"Contact '{params['contact']}' not found."})

    await log_contact_activity(
        db,
        contact_id=contact.id,
        activity_type=ActivityType.NOTE_ADDED,
        title="Note from O-Brain",
        description=params["note"],
        user_id=user_id,
    )

    display_name = contact.contact_name or contact.company_name
    return json.dumps({
        "success": True,
        "message": f"Note added to {display_name}'s timeline",
    })


async def _create_calendar_event(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a calendar event."""
    from app.calendar.service import create_event
    from app.calendar.schemas import CalendarEventCreate
    from app.calendar.models import EventType, Recurrence

    event_type_str = (params.get("event_type") or "reminder").upper()
    try:
        event_type = EventType[event_type_str]
    except KeyError:
        event_type = EventType.REMINDER

    data = CalendarEventCreate(
        title=params["title"],
        date=date.fromisoformat(params["date"]),
        event_type=event_type,
        description=params.get("description"),
        recurrence=Recurrence.NONE,
    )

    event = await create_event(db, user_id, data)
    return json.dumps({
        "success": True,
        "message": f"Calendar event created: '{params['title']}' on {params['date']}",
        "id": str(event.id),
    })


async def _create_proposal(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a draft proposal."""
    from app.proposals.service import create_proposal
    from app.proposals.schemas import ProposalCreate

    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    contact = await _resolve_contact(db, params["contact"])
    if not contact:
        return json.dumps({"error": f"Contact '{params['contact']}' not found."})

    # Build simple content JSON with description text
    desc_text = params.get("description") or params["title"]
    content_blocks = json.dumps([{
        "id": str(uuid.uuid4()),
        "type": "text",
        "data": {"text": desc_text},
        "order": 0,
    }])

    data = ProposalCreate(
        contact_id=contact.id,
        title=params["title"],
        value=Decimal(str(params["value"])),
        currency=params.get("currency", "USD"),
        content_json=content_blocks,
    )

    proposal = await create_proposal(db, data, user)
    contact_name = contact.contact_name or contact.company_name
    value = float(params["value"])

    logger.info("Created proposal '%s' for %s — $%.2f", params["title"], contact_name, value)
    return json.dumps({
        "success": True,
        "message": f"Draft proposal '{params['title']}' created for {contact_name} — ${value:,.2f}. View at /proposals/{proposal.id}",
        "id": str(proposal.id),
    })


async def _update_invoice_status(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Update an invoice's status."""
    from app.invoicing.models import Invoice

    invoice_ref = params["invoice"]

    # Try by invoice number first, then UUID
    result = await db.execute(
        select(Invoice).where(Invoice.invoice_number == invoice_ref)
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        try:
            inv_id = uuid.UUID(invoice_ref)
            result = await db.execute(select(Invoice).where(Invoice.id == inv_id))
            invoice = result.scalar_one_or_none()
        except (ValueError, AttributeError):
            pass

    if not invoice:
        return json.dumps({"error": f"Invoice '{invoice_ref}' not found."})

    new_status = params["status"].upper()
    old_status = _enum_val(invoice.status)
    invoice.status = new_status
    await db.commit()

    return json.dumps({
        "success": True,
        "message": f"Invoice {invoice.invoice_number} status changed from {old_status} to {new_status}",
    })


async def _create_booking(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a booking on the first available scheduling calendar."""
    from app.scheduling.service import create_booking, list_calendars
    from app.scheduling.schemas import BookingCreate

    # Find first calendar
    calendars, _ = await list_calendars(db, user_id, page=1, page_size=1)
    if not calendars:
        return json.dumps({"error": "No scheduling calendars exist. Create one first at /scheduling."})

    calendar = calendars[0]
    start_time = datetime.fromisoformat(params["start_time"])

    data = BookingCreate(
        guest_name=params["guest_name"],
        guest_email=params["guest_email"],
        start_time=start_time,
        guest_phone=params.get("guest_phone"),
        guest_notes=params.get("guest_notes"),
        meeting_type=params.get("meeting_type", "video"),
        meeting_location=params.get("meeting_location"),
    )

    booking = await create_booking(db, calendar.id, data)
    start_fmt = booking.start_time.strftime("%A, %B %d at %I:%M %p")

    logger.info("Created booking for %s on %s", params["guest_name"], start_fmt)
    return json.dumps({
        "success": True,
        "message": f"Booking created for {params['guest_name']} ({params['guest_email']}) on {start_fmt}. View at /scheduling",
        "id": str(booking.id),
    })


# ---------------------------------------------------------------------------
# Page / Website tools
# ---------------------------------------------------------------------------


async def _create_page(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a new landing page with AI-generated content."""
    from app.pages.service import create_page, ai_generate_page
    from app.pages.schemas import PageCreate
    from app.config import Settings

    settings = Settings()
    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    # Generate content
    result = await ai_generate_page(
        db,
        prompt=params["prompt"],
        style_preset=params.get("style_preset", "modern"),
        primary_color=params.get("primary_color"),
        font_family=params.get("font_family"),
        settings=settings,
    )

    # Create the page
    data = PageCreate(
        title=params["title"],
        style_preset=params.get("style_preset", "modern"),
        primary_color=params.get("primary_color"),
        font_family=params.get("font_family"),
    )
    page = await create_page(db, data, user)

    # Update with generated content
    from app.pages.models import Page as PageModel
    stmt = select(PageModel).where(PageModel.id == page.id)
    page_obj = (await db.execute(stmt)).scalar_one()
    page_obj.html_content = result.get("html_content", "")
    page_obj.css_content = result.get("css_content", "")
    page_obj.js_content = result.get("js_content", "")
    page_obj.sections_json = result.get("sections_json", "")
    await db.commit()

    logger.info("Created page '%s' via O-Brain", params["title"])
    return json.dumps({
        "success": True,
        "message": f"Landing page '{params['title']}' created! Open it at /pages/{page.id}/edit to preview and refine.",
        "page_id": str(page.id),
        "navigate_to": f"/pages/{page.id}/edit",
    })


async def _create_website(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Create a multi-page website with AI content."""
    from app.pages.service import create_website as ws_create, ai_generate_page
    from app.pages.models import Page as PageModel
    from app.config import Settings

    settings = Settings()
    user = await _get_user(db, user_id)
    if not user:
        return json.dumps({"error": "User not found"})

    ws = await ws_create(db, params["name"], None, user)

    # Update the default Home page and add others
    pages_data = params.get("pages", [{"title": "Home", "prompt": "A professional homepage", "is_homepage": True}])

    created_pages = []
    for i, p_data in enumerate(pages_data):
        if i == 0:
            # Update the auto-created home page
            stmt = select(PageModel).where(PageModel.website_id == ws.id).limit(1)
            page = (await db.execute(stmt)).scalar_one_or_none()
            if page:
                page.title = p_data["title"]
                page.slug = p_data.get("slug", p_data["title"].lower().replace(" ", "-"))
                page.is_homepage = p_data.get("is_homepage", True)
                page.page_order = i
        else:
            page = PageModel(
                id=uuid.uuid4(),
                title=p_data["title"],
                slug=p_data.get("slug", p_data["title"].lower().replace(" ", "-")),
                website_id=ws.id,
                page_order=i,
                is_homepage=p_data.get("is_homepage", False),
                created_by=user.id,
                style_preset=params.get("style_preset", "modern"),
                primary_color=params.get("primary_color"),
            )
            db.add(page)
            await db.flush()

        # Generate content
        try:
            result = await ai_generate_page(
                db,
                prompt=p_data["prompt"],
                style_preset=params.get("style_preset", "modern"),
                primary_color=params.get("primary_color"),
                settings=settings,
            )
            if page:
                page.html_content = result.get("html_content", "")
                page.css_content = result.get("css_content", "")
        except Exception as e:
            logger.warning("Failed to generate page '%s': %s", p_data["title"], e)

        created_pages.append(p_data["title"])

    await db.commit()

    logger.info("Created website '%s' with %d pages via O-Brain", params["name"], len(created_pages))
    return json.dumps({
        "success": True,
        "message": f"Website '{params['name']}' created with {len(created_pages)} pages: {', '.join(created_pages)}. Open it at /pages/website/{ws.id}/edit",
        "website_id": str(ws.id),
        "navigate_to": f"/pages/website/{ws.id}/edit",
    })


async def _query_page_analytics(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Query analytics for a specific page."""
    from app.pages.models import Page as PageModel
    from app.pages.service import get_page_analytics

    name = params.get("page_name", "")
    days = params.get("days", 30)

    # Find page by title or slug
    stmt = select(PageModel).where(
        __import__("sqlalchemy").or_(
            PageModel.title.ilike(f"%{name}%"),
            PageModel.slug.ilike(f"%{name}%"),
        )
    ).limit(1)
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()

    if not page:
        return json.dumps({"error": f"No page found matching '{name}'"})

    analytics = await get_page_analytics(db, page.id, days)
    analytics["page_title"] = page.title
    analytics["page_slug"] = page.slug
    analytics["page_status"] = page.status.value if hasattr(page.status, 'value') else str(page.status)

    return json.dumps(analytics, default=str)


async def _query_website_analytics(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Query aggregate analytics for a website."""
    from app.pages.models import Page as PageModel, Website
    from app.pages.service import get_page_analytics

    name = params.get("website_name", "")
    days = params.get("days", 30)

    stmt = select(Website).where(
        __import__("sqlalchemy").or_(
            Website.name.ilike(f"%{name}%"),
            Website.slug.ilike(f"%{name}%"),
        )
    ).limit(1)
    result = await db.execute(stmt)
    ws = result.scalar_one_or_none()

    if not ws:
        return json.dumps({"error": f"No website found matching '{name}'"})

    # Get all pages
    pages_stmt = select(PageModel).where(PageModel.website_id == ws.id)
    pages_result = await db.execute(pages_stmt)
    pages = pages_result.scalars().all()

    total_views = 0
    total_unique = 0
    total_submissions = 0
    page_breakdown = []

    for page in pages:
        analytics = await get_page_analytics(db, page.id, days)
        total_views += analytics["total_views"]
        total_unique += analytics["unique_visitors"]
        total_submissions += analytics["total_submissions"]
        page_breakdown.append({
            "title": page.title,
            "slug": page.slug,
            "views": analytics["total_views"],
            "unique_visitors": analytics["unique_visitors"],
            "conversion_rate": analytics["conversion_rate"],
        })

    page_breakdown.sort(key=lambda x: x["views"], reverse=True)

    return json.dumps({
        "website_name": ws.name,
        "total_views": total_views,
        "total_unique_visitors": total_unique,
        "total_submissions": total_submissions,
        "overall_conversion_rate": round(total_submissions / total_views * 100, 2) if total_views else 0,
        "pages": page_breakdown,
    }, default=str)


# ---------------------------------------------------------------------------
# ACTION tools — create drafts that require user confirmation
# ---------------------------------------------------------------------------


async def _create_pending_action(
    db: AsyncSession,
    user_id: uuid.UUID,
    action_type: str,
    data: dict,
) -> dict:
    """Create a BrainPendingAction record and return its info."""
    from app.brain.models import BrainPendingAction, PendingActionType, PendingActionStatus

    # Get the user's most recent conversation
    from app.brain.models import BrainConversation
    stmt = select(BrainConversation).where(
        BrainConversation.user_id == user_id
    ).order_by(desc(BrainConversation.updated_at)).limit(1)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        return {"error": "No active conversation"}

    action = BrainPendingAction(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        user_id=user_id,
        action_type=PendingActionType(action_type),
        status=PendingActionStatus.PENDING,
        data_json=json.dumps(data),
    )
    db.add(action)
    await db.commit()

    return {
        "action_id": str(action.id),
        "action_type": action_type,
        "status": "drafted",
        "data": data,
    }


async def _draft_email(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Draft an email for user confirmation."""
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")

    if not to or not subject:
        return json.dumps({"error": "Email requires 'to' and 'subject' fields"})

    action = await _create_pending_action(db, user_id, "send_email", {
        "to": to,
        "subject": subject,
        "body": body,
    })

    if "error" in action:
        return json.dumps(action)

    logger.info("Drafted email to %s: '%s' (action %s)", to, subject, action["action_id"])
    return json.dumps({
        "status": "drafted",
        "action_id": action["action_id"],
        "message": f"Email draft created to {to} with subject \"{subject}\". The user must review and confirm before it is sent.",
        "preview": {"to": to, "subject": subject, "body_preview": body[:200]},
    })


async def _draft_sms(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Draft an SMS for user confirmation."""
    to = params.get("to", "")
    message = params.get("message", "")

    if not to or not message:
        return json.dumps({"error": "SMS requires 'to' and 'message' fields"})

    char_count = len(message)
    action = await _create_pending_action(db, user_id, "send_sms", {
        "to": to,
        "message": message,
    })

    if "error" in action:
        return json.dumps(action)

    logger.info("Drafted SMS to %s (%d chars, action %s)", to, char_count, action["action_id"])
    return json.dumps({
        "status": "drafted",
        "action_id": action["action_id"],
        "message": f"SMS draft created to {to} ({char_count} chars). The user must review and confirm before it is sent.",
        "preview": {"to": to, "message": message, "char_count": char_count},
    })


async def _draft_document(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Draft a document for user confirmation."""
    title = params.get("title", "")
    content = params.get("content", "")

    if not title:
        return json.dumps({"error": "Document requires a 'title'"})

    action = await _create_pending_action(db, user_id, "create_document", {
        "title": title,
        "content": content,
    })

    if "error" in action:
        return json.dumps(action)

    logger.info("Drafted document '%s' (action %s)", title, action["action_id"])
    return json.dumps({
        "status": "drafted",
        "action_id": action["action_id"],
        "message": f"Document \"{title}\" drafted. The user must confirm to create it in the Docs editor.",
        "preview": {"title": title, "content_preview": content[:300]},
    })


async def _draft_save_to_drive(db: AsyncSession, user_id: uuid.UUID, params: dict) -> str:
    """Draft a file save for user confirmation."""
    filename = params.get("filename", "")
    content = params.get("content", "")
    folder = params.get("folder", "")

    if not filename:
        return json.dumps({"error": "Requires a 'filename'"})

    action = await _create_pending_action(db, user_id, "save_to_drive", {
        "filename": filename,
        "content": content,
        "folder": folder,
    })

    if "error" in action:
        return json.dumps(action)

    folder_label = f" in '{folder}'" if folder else ""
    logger.info("Drafted save '%s'%s (action %s)", filename, folder_label, action["action_id"])
    return json.dumps({
        "status": "drafted",
        "action_id": action["action_id"],
        "message": f"File \"{filename}\" ready to save{folder_label}. The user must confirm.",
        "preview": {"filename": filename, "folder": folder, "size": len(content)},
    })
