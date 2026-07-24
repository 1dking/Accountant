"""General Ledger & Trial Balance — the unified double-entry reports.

These are computed on the fly over TWO posting sources, which is the whole point
of the Phase-1 design (see ledger_models docstring): the journal and the cashbook
are never merged in storage, so they can't drift.

1. **Journal lines** of POSTED entries — already double-entry, used verbatim.
2. **Cashbook entries** — the legacy single-entry tracker, expanded into balanced
   postings via the CoA mappings:
     * income  → Dr <payment-account asset>   Cr <category income>
     * expense → Dr <category expense>         Cr <payment-account asset>

Category/payment-account → CoA resolution is per-tenant and name-based (the
``coa_account_id`` cache is only trusted when the account belongs to the tenant),
falling back to the seeded catch-alls (4900 Other Income / 6900 Other Expenses /
1500 Undeposited Funds), and finally to a synthetic "Unmapped" bucket if the CoA
was never seeded. Because every cashbook entry contributes equal debit and credit,
the Trial Balance always balances regardless of how accounts resolve.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.accounting.ledger_models import (
    NORMAL_BALANCE,
    AccountType,
    ChartAccount,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from app.auth.models import User
from app.cashbook.models import CashbookEntry, EntryType, PaymentAccount, TransactionCategory
from app.core.authorization import apply_cashbook_filter

_ZERO = Decimal("0.00")

# Seeded catch-all codes the resolver falls back to.
_FALLBACK_INCOME = "4900"
_FALLBACK_EXPENSE = "6900"
_FALLBACK_ASSET = "1500"


@dataclass
class Posting:
    account_key: str
    code: str
    name: str
    account_type: AccountType
    normal_balance: str
    date: date
    debit: Decimal
    credit: Decimal
    source: str  # "journal" | "cashbook"
    ref: str
    memo: str | None = None


@dataclass
class _Bucket:
    """A synthetic account used when the CoA has no home for a mapping."""

    key: str
    code: str
    name: str
    account_type: AccountType

    @property
    def normal_balance(self) -> str:
        return NORMAL_BALANCE[self.account_type]


@dataclass
class _Resolver:
    by_id: dict[uuid.UUID, ChartAccount]
    by_name: dict[tuple[str, AccountType], ChartAccount]
    by_code: dict[str, ChartAccount]
    buckets: dict[str, _Bucket] = field(default_factory=dict)

    def _bucket(self, key: str, code: str, name: str, t: AccountType):
        b = self.buckets.get(key)
        if b is None:
            b = _Bucket(key=key, code=code, name=name, account_type=t)
            self.buckets[key] = b
        return b

    def category_account(self, cat: TransactionCategory | None, entry_type: EntryType):
        want = AccountType.INCOME if entry_type == EntryType.INCOME else AccountType.EXPENSE
        if cat is not None:
            if cat.coa_account_id and cat.coa_account_id in self.by_id:
                acct = self.by_id[cat.coa_account_id]
                if acct.account_type == want:
                    return acct
            hit = self.by_name.get((cat.name.strip().lower(), want))
            if hit is not None:
                return hit
        fallback_code = _FALLBACK_INCOME if want == AccountType.INCOME else _FALLBACK_EXPENSE
        if fallback_code in self.by_code:
            return self.by_code[fallback_code]
        label = "Unmapped Income" if want == AccountType.INCOME else "Unmapped Expense"
        return self._bucket(f"unmapped:{want.value}", fallback_code, label, want)

    def payment_account(self, pa: PaymentAccount | None):
        if pa is not None:
            if pa.coa_account_id and pa.coa_account_id in self.by_id:
                return self.by_id[pa.coa_account_id]
            hit = self.by_name.get((pa.name.strip().lower(), AccountType.ASSET))
            if hit is not None:
                return hit
        if _FALLBACK_ASSET in self.by_code:
            return self.by_code[_FALLBACK_ASSET]
        return self._bucket("unmapped:asset", _FALLBACK_ASSET, "Unmapped Cash", AccountType.ASSET)


async def _build_resolver(db: AsyncSession, user: User) -> _Resolver:
    stmt = select(ChartAccount)
    stmt = apply_cashbook_filter(stmt, ChartAccount.user_id, ChartAccount.org_id, user)
    accts = list((await db.execute(stmt)).scalars().all())
    return _Resolver(
        by_id={a.id: a for a in accts},
        by_name={(a.name.strip().lower(), a.account_type): a for a in accts},
        by_code={a.code: a for a in accts},
    )


def _acct_fields(acct) -> tuple[str, str, str, AccountType, str]:
    """(account_key, code, name, type, normal_balance) for a real account or bucket."""
    if isinstance(acct, _Bucket):
        return acct.key, acct.code, acct.name, acct.account_type, acct.normal_balance
    return str(acct.id), acct.code, acct.name, acct.account_type, acct.normal_balance


async def gather_postings(
    db: AsyncSession,
    user: User,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Posting]:
    resolver = await _build_resolver(db, user)
    postings: list[Posting] = []

    # --- Journal lines of POSTED entries -----------------------------------
    jstmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines).selectinload(JournalLine.account))
        .where(JournalEntry.status == JournalEntryStatus.POSTED)
    )
    jstmt = apply_cashbook_filter(jstmt, JournalEntry.user_id, JournalEntry.org_id, user)
    if date_from:
        jstmt = jstmt.where(JournalEntry.date >= date_from)
    if date_to:
        jstmt = jstmt.where(JournalEntry.date <= date_to)
    for entry in (await db.execute(jstmt)).scalars().unique().all():
        for ln in entry.lines:
            if ln.account is None:
                continue
            key, code, name, atype, nb = _acct_fields(ln.account)
            postings.append(
                Posting(
                    account_key=key, code=code, name=name, account_type=atype,
                    normal_balance=nb, date=entry.date,
                    debit=Decimal(str(ln.debit)), credit=Decimal(str(ln.credit)),
                    source="journal", ref=f"JE-{entry.entry_number}", memo=entry.memo,
                )
            )

    # --- Cashbook entries, expanded ---------------------------------------
    cstmt = (
        select(CashbookEntry)
        .options(
            selectinload(CashbookEntry.category),
            selectinload(CashbookEntry.account),
            selectinload(CashbookEntry.split_children).selectinload(CashbookEntry.category),
        )
        .where(
            CashbookEntry.is_deleted.is_(False),
            CashbookEntry.split_parent_id.is_(None),  # top-level only; children via parent
        )
    )
    cstmt = apply_cashbook_filter(cstmt, CashbookEntry.user_id, CashbookEntry.org_id, user)
    if date_from:
        cstmt = cstmt.where(CashbookEntry.date >= date_from)
    if date_to:
        cstmt = cstmt.where(CashbookEntry.date <= date_to)

    for e in (await db.execute(cstmt)).scalars().unique().all():
        is_income = e.entry_type == EntryType.INCOME
        cash = resolver.payment_account(e.account)
        ck, ccode, cname, ctype, cnb = _acct_fields(cash)
        total = Decimal(str(e.total_amount))
        ref = f"CB-{str(e.id)[:8]}"

        # Cash (asset) side: income increases cash (debit), expense reduces it (credit).
        postings.append(
            Posting(
                account_key=ck, code=ccode, name=cname, account_type=ctype,
                normal_balance=cnb, date=e.date,
                debit=(total if is_income else _ZERO),
                credit=(_ZERO if is_income else total),
                source="cashbook", ref=ref, memo=e.description,
            )
        )

        # Category (income/expense) side: split across children if present.
        breakdown = e.split_children if e.split_children else [e]
        for part in breakdown:
            cat_acct = resolver.category_account(part.category, e.entry_type)
            ak, acode, aname, atype, anb = _acct_fields(cat_acct)
            amt = Decimal(str(part.total_amount))
            postings.append(
                Posting(
                    account_key=ak, code=acode, name=aname, account_type=atype,
                    normal_balance=anb, date=e.date,
                    debit=(_ZERO if is_income else amt),
                    credit=(amt if is_income else _ZERO),
                    source="cashbook", ref=ref, memo=part.description,
                )
            )

    return postings


def trial_balance(postings: list[Posting]) -> dict:
    """Aggregate postings into a Trial Balance: one row per account, net placed in
    its normal-balance column. Also returns column totals (which must be equal)."""
    agg: dict[str, dict] = {}
    for p in postings:
        row = agg.setdefault(
            p.account_key,
            {
                "account_key": p.account_key, "code": p.code, "name": p.name,
                "account_type": p.account_type.value, "normal_balance": p.normal_balance,
                "debit": _ZERO, "credit": _ZERO,
            },
        )
        row["debit"] += p.debit
        row["credit"] += p.credit

    rows = []
    total_debit = _ZERO
    total_credit = _ZERO
    for row in agg.values():
        net = row["debit"] - row["credit"]
        debit_bal = credit_bal = _ZERO
        if row["normal_balance"] == "debit":
            if net >= 0:
                debit_bal = net
            else:
                credit_bal = -net
        else:
            if net <= 0:
                credit_bal = -net
            else:
                debit_bal = net
        if debit_bal == _ZERO and credit_bal == _ZERO:
            continue  # net-zero accounts are omitted
        total_debit += debit_bal
        total_credit += credit_bal
        rows.append(
            {
                "code": row["code"], "name": row["name"],
                "account_type": row["account_type"],
                "debit": debit_bal, "credit": credit_bal,
            }
        )

    rows.sort(key=lambda r: r["code"])
    return {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    }


def general_ledger(postings: list[Posting]) -> dict:
    """Group postings by account, ordered by date, with a running balance in the
    account's normal-balance direction."""
    by_acct: dict[str, dict] = {}
    for p in postings:
        acct = by_acct.setdefault(
            p.account_key,
            {
                "code": p.code, "name": p.name,
                "account_type": p.account_type.value,
                "normal_balance": p.normal_balance, "_postings": [],
            },
        )
        acct["_postings"].append(p)

    accounts = []
    for acct in by_acct.values():
        acct["_postings"].sort(key=lambda p: (p.date, p.ref))
        running = _ZERO
        lines = []
        total_debit = total_credit = _ZERO
        sign = 1 if acct["normal_balance"] == "debit" else -1
        for p in acct["_postings"]:
            running += sign * (p.debit - p.credit)
            total_debit += p.debit
            total_credit += p.credit
            lines.append(
                {
                    "date": p.date.isoformat(), "ref": p.ref, "source": p.source,
                    "memo": p.memo, "debit": p.debit, "credit": p.credit,
                    "balance": running,
                }
            )
        accounts.append(
            {
                "code": acct["code"], "name": acct["name"],
                "account_type": acct["account_type"],
                "normal_balance": acct["normal_balance"],
                "postings": lines,
                "total_debit": total_debit, "total_credit": total_credit,
                "closing_balance": running,
            }
        )

    accounts.sort(key=lambda a: a["code"])
    return {"accounts": accounts}
