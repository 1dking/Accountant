"""Smart Import — CSV statement parsing + AI-response hardening.

Covers the two fixes that make Smart Import actually read what it's given:
  1. Deterministic CSV parsing (Meta/Facebook Ads, generic bank exports) — one
     row per payment, totals/GST skipped, provider → category/direction.
  2. Robust parsing of the AI response (fences, prose, truncation) so a long
     statement no longer silently fails to zero rows.
And the end-to-end CSV → review → confirm path, including category resolution.
"""
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.cashbook.models import (
    AccountType,
    CashbookEntry,
    CategoryType,
    PaymentAccount,
    TransactionCategory,
)
from app.smart_import import service
from app.smart_import.csv_parser import (
    parse_amount,
    parse_date_iso,
    parse_statement_csv,
)

# A compact Meta/Facebook Ads billing export: preamble, a charges table, a
# totals line, an ad-credit table, and a GST footer.
META_CSV = """Meta information
"Meta Platforms, Inc.",1 Meta Way,"Menlo Park, CA 94025",United States

Advertiser Information
Account: 319984961911525

Billing Report: 11/1/2023 - 7/26/2025

Meta Ads payment
Date,Transaction ID,Payment Method,Amount,Currency
5/31/2025,23894890253530901-9900292030083950,Visa 9905,297.90,CAD
4/22/2025,9692197574226735-9704671462979344,MasterCard 3757,297.59,CAD
4/21/2025,9766835340096295-9645905362189287,Visa 4878,42.50,CAD
,,Total Amount Billed,"637.99",CAD

Meta Ads payment
Payment Method: Ad Credit
Date,Transaction ID,Amount,Currency
10/7/2024,8464757786970728-8388731227906712,0.03,CAD
,Total Amount Billed,0.03,CAD

GST Rate: 13%
GST Amount: 82.90
"""


# ---------------------------------------------------------------------------
# Pure parser
# ---------------------------------------------------------------------------


def test_parse_amount_handles_symbols_commas_parens():
    assert parse_amount("$1,412.50") == 1412.50
    assert parse_amount("297.90") == 297.90
    assert parse_amount("(50.00)") == -50.0  # parenthesised negative
    assert parse_amount("") is None
    assert parse_amount("N/A") is None


def test_parse_date_iso_formats():
    assert parse_date_iso("5/31/2025") == "2025-05-31"   # US M/D/Y (Meta)
    assert parse_date_iso("2025-01-02") == "2025-01-02"
    assert parse_date_iso("") is None
    assert parse_date_iso("not a date") is None


def test_meta_csv_extracts_each_payment():
    parsed = parse_statement_csv(META_CSV, "invoice_summary.csv")
    assert parsed["provider"] == "Meta Ads"
    txns = parsed["transactions"]
    # 3 charges + 1 ad credit = 4; the two "Total Amount Billed" lines and the
    # GST footer are NOT transactions.
    assert len(txns) == 4
    assert all(t["entry_type"] == "expense" for t in txns)
    assert all(t["category_suggestion"] == "Advertising" for t in txns)
    assert all(t["date"] is not None for t in txns)
    assert txns[0]["date"] == "2025-05-31"
    assert txns[0]["amount"] == 297.90
    # No totals leaked in.
    amounts = {t["amount"] for t in txns}
    assert 637.99 not in amounts
    assert 82.90 not in amounts


def test_generic_csv_with_date_desc_amount():
    csv_text = "Date,Description,Amount\n2025-03-01,Office chairs,120.00\n2025-03-05,Domain renewal,18.00\n"
    txns = parse_statement_csv(csv_text, "expenses.csv")["transactions"]
    assert len(txns) == 2
    assert txns[0]["date"] == "2025-03-01"
    assert txns[0]["amount"] == 120.0
    assert "Office chairs" in txns[0]["description"]


def test_csv_without_a_transaction_table_reads_nothing_with_reason():
    parsed = parse_statement_csv("Just some notes\nno tabular data here\n", "notes.csv")
    assert parsed["transactions"] == []
    assert "Date and Amount" in parsed["summary"]  # actionable explanation


# ---------------------------------------------------------------------------
# AI response hardening
# ---------------------------------------------------------------------------


def _resp(text=None, *, stop_reason="end_turn", blocks=None):
    if blocks is None:
        blocks = [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def test_parse_ai_json_plain_and_fenced():
    payload = '{"document_type":"invoice","transactions":[]}'
    assert service._parse_ai_json(_resp(payload))["document_type"] == "invoice"
    fenced = f"```json\n{payload}\n```"
    assert service._parse_ai_json(_resp(fenced))["document_type"] == "invoice"


def test_parse_ai_json_tolerates_prose_around_json():
    text = 'Here is the data you asked for:\n{"transactions": [{"amount": 5}]}\nHope that helps!'
    data = service._parse_ai_json(_resp(text))
    assert data["transactions"][0]["amount"] == 5


def test_parse_ai_json_concatenates_multiple_text_blocks():
    blocks = [
        SimpleNamespace(type="text", text='{"transactions":'),
        SimpleNamespace(type="text", text='[{"amount": 9}]}'),
    ]
    data = service._parse_ai_json(_resp(blocks=blocks))
    assert data["transactions"][0]["amount"] == 9


def test_parse_ai_json_truncation_raises_actionable_error():
    # A statement too long for one pass must surface a clear message, not a
    # cryptic JSON error (this was the silent "reads nothing" failure).
    with pytest.raises(ValueError) as ei:
        service._parse_ai_json(_resp('{"transactions": [{"amo', stop_reason="max_tokens"))
    assert "CSV" in str(ei.value)


def test_parse_ai_json_garbage_raises():
    with pytest.raises(ValueError):
        service._parse_ai_json(_resp("I could not read this document."))


# ---------------------------------------------------------------------------
# End-to-end: CSV upload path → confirm → cashbook (with category resolution)
# ---------------------------------------------------------------------------


async def _mk_user(db) -> User:
    u = User(
        id=uuid.uuid4(), email="op@ocidm.io", hashed_password=hash_password("TestPass123!"),
        full_name="Op", role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _mk_account(db, user) -> PaymentAccount:
    a = PaymentAccount(
        user_id=user.id, name="Business Visa", account_type=AccountType.CREDIT_CARD,
        currency="CAD", opening_balance=0, opening_balance_date=date(2023, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def test_process_csv_then_confirm_posts_and_resolves_category(db):
    user = await _mk_user(db)
    account = await _mk_account(db, user)
    db.add(TransactionCategory(name="Advertising", category_type=CategoryType.EXPENSE))
    await db.commit()

    imp = await service.create_import(
        db, user, filename="invoice_summary.csv", storage_path="x",
        mime_type="text/csv", file_size=len(META_CSV),
    )
    imp = await service.process_csv_import(db, imp.id, META_CSV.encode())

    assert imp.status == "ready"
    assert len(imp.items) == 4  # one row per payment, no totals/GST

    result = await service.confirm_import(db, imp.id, user.id, account.id, None)
    assert result["imported_count"] == 4
    assert not result["errors"]

    entries = (await db.execute(
        select(CashbookEntry).where(CashbookEntry.user_id == user.id)
    )).scalars().all()
    assert len(entries) == 4
    # source tagged, and the "Advertising" suggestion resolved to a real category.
    assert all(e.source == "smart_import" for e in entries)
    adv = (await db.execute(
        select(TransactionCategory).where(TransactionCategory.name == "Advertising")
    )).scalar_one()
    assert all(e.category_id == adv.id for e in entries)


async def test_process_csv_with_no_table_marks_failed_with_reason(db):
    user = await _mk_user(db)
    imp = await service.create_import(
        db, user, filename="notes.csv", storage_path="x",
        mime_type="text/csv", file_size=10,
    )
    imp = await service.process_csv_import(db, imp.id, b"hello\nworld\n")
    assert imp.status == "failed"
    assert imp.error_message  # explains why nothing was read
    assert len(imp.items) == 0
