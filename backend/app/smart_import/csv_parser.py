"""Deterministic parser for CSV statement / export files.

Smart Import's AI path reads receipts and PDF statements, but many providers
(Meta/Facebook Ads, Stripe, banks) let you export a CSV — structured data we can
parse EXACTLY, for free, with no model call and no truncation risk. This module
turns such a CSV into the same ``transactions`` shape the AI path produces, so
the rest of Smart Import (review table → confirm → cashbook) is unchanged.

Design: a CSV statement is a sequence of sections, each an optional preamble
followed by a header row (containing a date-ish and an amount-ish column) and
then data rows, ending at a blank line or a totals/tax line. We scan for those
tables generically and emit one transaction per data row, so it handles the Meta
billing export (two sections: charges + ad credits, plus a GST footer) as well
as a plain bank/Stripe export — without a per-provider template.

Pure and side-effect free so it can be unit-tested directly.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Optional, TypedDict

# Header tokens. A row is a table header if it has BOTH a date column and an
# amount column. Kept broad but specific enough not to match id/currency cells.
_DATE_KEYS = ("date", "created", "posted", "charge date", "transaction date")
_AMOUNT_KEYS = (
    "amount", "gross", "net", "total amount", "charge amount",
    "converted amount", "amount billed", "debit", "credit",
)
# Columns we prefer, in order, when building a row description.
_DESC_KEYS = (
    "description", "name", "merchant", "payee", "memo", "details",
    "payment method", "customer", "customer email", "transaction id",
)
# A data cell containing any of these marks a totals/tax/summary line to skip
# (and ends the current section).
_SKIP_TOKENS = (
    "total", "subtotal", "grand total", "cumulative", "gst", "hst",
    "vat", "tax rate", "tax amount", "balance",
)

_DATE_FORMATS = (
    "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y",
    "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    "%b %d %Y", "%Y-%m-%dT%H:%M:%S",
)


class Transaction(TypedDict):
    entry_type: str
    date: Optional[str]
    description: str
    amount: float
    tax_amount: Optional[float]
    category_suggestion: Optional[str]


class ParsedCsv(TypedDict):
    document_type: str
    summary: str
    provider: str
    transactions: list[Transaction]


# --- provider fingerprints: (needle in raw text) -> (label, category, direction)
_PROVIDERS = [
    (("meta platforms", "meta ads", "facebook"), "Meta Ads", "Advertising", "expense"),
    (("google ads", "google llc"), "Google Ads", "Advertising", "expense"),
    (("stripe",), "Stripe", "Fees", "income"),
    (("gohighlevel", "highlevel"), "HighLevel", "Dues & Subscriptions", "expense"),
    (("rogers",), "Rogers", "Utilities", "expense"),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def parse_date_iso(value: str) -> Optional[str]:
    """Parse a date cell into ISO ``YYYY-MM-DD`` (or None if unparseable)."""
    v = (value or "").strip()
    if not v:
        return None
    v = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", v)  # 3rd -> 3
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_amount(value: str) -> Optional[float]:
    """Parse an amount cell. Handles $, thousands commas, and (parens) negatives."""
    v = (value or "").strip()
    if not v:
        return None
    neg = v.startswith("(") and v.endswith(")")
    v = v.replace("(", "").replace(")", "")
    v = re.sub(r"[^0-9.\-]", "", v)  # drop $, commas, currency codes, spaces
    if v in ("", "-", ".", "-."):
        return None
    try:
        amount = float(v)
    except ValueError:
        return None
    return -amount if neg else amount


def _detect_provider(raw_text: str) -> tuple[str, Optional[str], str]:
    """Return (provider_label, default_category, default_entry_type)."""
    low = raw_text.lower()
    for needles, label, category, direction in _PROVIDERS:
        if any(n in low for n in needles):
            return label, category, direction
    return "", None, "expense"


def _find_columns(header: list[str]) -> Optional[tuple[int, int, list[int]]]:
    """If ``header`` is a transaction table header, return
    (date_idx, amount_idx, description_idxs); else None."""
    norm = [_norm(c) for c in header]
    date_idx = amount_idx = None
    for i, cell in enumerate(norm):
        if date_idx is None and any(k == cell or k in cell for k in _DATE_KEYS):
            date_idx = i
    # Prefer an exact "amount" column; else the first amount-ish column.
    for i, cell in enumerate(norm):
        if cell == "amount":
            amount_idx = i
            break
    if amount_idx is None:
        for i, cell in enumerate(norm):
            if any(k in cell for k in _AMOUNT_KEYS):
                amount_idx = i
                break
    if date_idx is None or amount_idx is None or date_idx == amount_idx:
        return None
    # Description columns: preferred keys first (in _DESC_KEYS order), then any
    # other non-date/amount column as a fallback.
    desc_idxs: list[int] = []
    for key in _DESC_KEYS:
        for i, cell in enumerate(norm):
            if i in (date_idx, amount_idx) or i in desc_idxs:
                continue
            if key in cell:
                desc_idxs.append(i)
    return date_idx, amount_idx, desc_idxs


def _looks_like_total(row: list[str]) -> bool:
    joined = _norm(" ".join(row))
    return any(tok in joined for tok in _SKIP_TOKENS)


def parse_statement_csv(text: str, filename: str = "") -> ParsedCsv:
    """Parse CSV statement text into the Smart Import transaction shape."""
    # Tolerate a UTF-8 BOM.
    if text and text[0] == "﻿":
        text = text[1:]

    provider, default_category, default_type = _detect_provider(text + " " + filename)

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader]

    transactions: list[Transaction] = []
    cols: Optional[tuple[int, int, list[int]]] = None

    for row in rows:
        if not any((c or "").strip() for c in row):
            cols = None  # blank line ends a section
            continue

        header = _find_columns(row)
        if header is not None:
            cols = header
            continue

        if cols is None:
            continue  # preamble / metadata before any table

        date_idx, amount_idx, desc_idxs = cols

        def _cell(i: int) -> str:
            return row[i].strip() if i < len(row) and row[i] is not None else ""

        date_iso = parse_date_iso(_cell(date_idx))
        amount = parse_amount(_cell(amount_idx))

        # A totals/tax/summary line (a skip token with no real date) ends the
        # section rather than becoming a transaction. Requiring the date to be
        # absent avoids dropping a genuine dated row that merely contains a word
        # like "total" or "balance" in its description.
        if _looks_like_total(row) and date_iso is None:
            cols = None
            continue
        if amount is None or amount == 0:
            continue  # not a real data row (or a $0 line)

        # Use the single highest-priority description column (e.g. Payment Method
        # over a long Transaction ID), not every text column joined together.
        detail = ""
        for i in desc_idxs:
            if _cell(i):
                detail = _cell(i)
                break
        label = provider or (filename.rsplit(".", 1)[0] if filename else "Statement")
        description = f"{label} — {detail}" if detail else f"{label} payment"
        description = description[:500]

        transactions.append(Transaction(
            entry_type=default_type,
            date=date_iso,
            description=description,
            amount=abs(amount),
            tax_amount=None,
            category_suggestion=default_category,
        ))

    summary = (
        f"{provider or 'CSV'} statement — {len(transactions)} transaction(s) parsed"
        if transactions else
        "No transactions could be read from this CSV. Check that it has a Date and Amount column."
    )
    return ParsedCsv(
        document_type="csv_statement",
        summary=summary,
        provider=provider,
        transactions=transactions,
    )
