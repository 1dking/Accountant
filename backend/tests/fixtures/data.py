"""Shared realistic test data for the entire test suite."""

from datetime import date, timedelta
from decimal import Decimal


# ---------------------------------------------------------------------------
# Contact data
# ---------------------------------------------------------------------------

CONTACTS = {
    "acme": {
        "type": "client",
        "company_name": "Acme Corp",
        "contact_name": "John Doe",
        "email": "john@acme.com",
        "phone": "+1-555-0100",
        "address_line1": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "US",
        "tax_id": "12-3456789",
    },
    "globex": {
        "type": "client",
        "company_name": "Globex Inc",
        "contact_name": "Alice Johnson",
        "email": "alice@globex.com",
        "phone": "+1-555-0200",
        "city": "Chicago",
        "state": "IL",
        "country": "US",
    },
    "supply_co": {
        "type": "vendor",
        "company_name": "SupplyCo LLC",
        "contact_name": "Jane Smith",
        "email": "jane@supplyco.com",
        "country": "US",
    },
}


# ---------------------------------------------------------------------------
# Invoice data
# ---------------------------------------------------------------------------

def make_invoice_payload(contact_id: str, **overrides) -> dict:
    """Build a valid invoice create payload."""
    base = {
        "contact_id": contact_id,
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "tax_rate": "10.00",
        "discount_amount": "0.00",
        "currency": "USD",
        "notes": "Test invoice",
        "line_items": [
            {
                "description": "Consulting Services",
                "quantity": "10",
                "unit_price": "150.00",
                "tax_rate": "10.00",
            },
        ],
    }
    base.update(overrides)
    return base


def make_multi_line_invoice(contact_id: str) -> dict:
    """Invoice with multiple line items for math verification."""
    return {
        "contact_id": contact_id,
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "tax_rate": "7.25",
        "discount_amount": "50.00",
        "currency": "USD",
        "line_items": [
            {"description": "Web Design", "quantity": "1", "unit_price": "2500.00"},
            {"description": "Hosting (annual)", "quantity": "1", "unit_price": "360.00"},
            {"description": "Domain Name", "quantity": "3", "unit_price": "15.99"},
        ],
    }


# ---------------------------------------------------------------------------
# Expense data
# ---------------------------------------------------------------------------

def make_expense_payload(**overrides) -> dict:
    base = {
        "vendor_name": "Office Depot",
        "description": "Office supplies",
        "amount": "125.50",
        "currency": "USD",
        "date": date.today().isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Cashbook data
# ---------------------------------------------------------------------------

def make_cashbook_entry(account_id: str, **overrides) -> dict:
    base = {
        "account_id": account_id,
        "entry_type": "income",
        "date": date.today().isoformat(),
        "description": "Client payment",
        "total_amount": "500.00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Budget data
# ---------------------------------------------------------------------------

def make_budget_payload(**overrides) -> dict:
    base = {
        "name": "Marketing Budget Q1",
        "amount": "5000.00",
        "period_type": "monthly",
        "start_date": date.today().replace(day=1).isoformat(),
        "end_date": (date.today().replace(day=1) + timedelta(days=30)).isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Income data
# ---------------------------------------------------------------------------

def make_income_payload(**overrides) -> dict:
    base = {
        "category": "service",
        "description": "Consulting payment",
        "amount": "2500.00",
        "currency": "USD",
        "date": date.today().isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Rounding test cases — hand-calculated expected values
# ---------------------------------------------------------------------------

ROUNDING_CASES = [
    {
        "name": "Split $100 three ways",
        "total": Decimal("100.00"),
        "splits": 3,
        "expected": [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")],
    },
    {
        "name": "7.25% tax on $33.33",
        "amount": Decimal("33.33"),
        "tax_rate": Decimal("7.25"),
        "expected_tax": Decimal("2.42"),
        "expected_total": Decimal("35.75"),
    },
    {
        "name": "15% discount then 13% tax on $1847.50",
        "subtotal": Decimal("1847.50"),
        "discount_pct": Decimal("15"),
        "tax_rate": Decimal("13"),
        "expected_after_discount": Decimal("1570.38"),
        "expected_tax": Decimal("204.15"),
        "expected_total": Decimal("1774.53"),
    },
]


# ---------------------------------------------------------------------------
# Adversarial payloads
# ---------------------------------------------------------------------------

MALICIOUS_FILENAMES = [
    "../../../etc/passwd",
    "file<script>alert(1)</script>.pdf",
    "file\x00hidden.pdf",
    "CON.pdf",         # Windows reserved name
    "   spaces   .pdf",
    "file\ud83d\ude00emoji.pdf",
    "a" * 500 + ".pdf",  # very long filename
]

XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "{{constructor.constructor('return this')()}}",
]

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1 OR 1=1",
    "' UNION SELECT * FROM users --",
    "1; SELECT pg_sleep(5) --",
    "admin'--",
]

FINANCIAL_ABUSE_AMOUNTS = [
    "-100.00",
    "0.00",
    "0.001",          # sub-penny
    "999999999.99",   # absurdly large
    "-0.01",
]
