"""Canadian sales-tax matrix: provinces, system rates, and the resolver that
turns "this business is in BC" into "GST 5% + PST 7%".

Rates are as of 2026-09. Sources: CRA GST/HST rates page; provincial
finance ministries. NS dropped HST from 15% to 14% on 2025-04-01 — the
``effective_from`` column exists so a future change can coexist with the old
rate rather than overwrite it.

Two things this module deliberately does NOT do:
- It never posts to the ledger or touches Personal mode.
- It never invents a rate — if a province is unknown the caller gets None
  and must fall back to the tenant's explicit default_tax_rate_id.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounting.tax_models import TaxRate

logger = logging.getLogger(__name__)

#: ISO-3166-2:CA subdivision codes. Order is display order.
PROVINCES: dict[str, str] = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}

TaxType = str  # "gst" | "hst" | "pst" | "rst" | "qst" | "other"

#: (name, tax_type, province, rate %, is_recoverable, effective_from)
#: is_recoverable = eligible as an input tax credit on the GST/HST return.
#: BC/SK/MB PST is NOT recoverable (it's a cost). QST is recoverable via ITR
#: on the QST return, which Revenu Québec administers alongside GST.
SYSTEM_RATES: list[tuple[str, TaxType, str | None, float, bool, date | None]] = [
    ("GST 5%",           "gst", None, 5.0,   True,  None),
    ("HST 13% (ON)",     "hst", "ON", 13.0,  True,  None),
    ("HST 14% (NS)",     "hst", "NS", 14.0,  True,  date(2025, 4, 1)),
    ("HST 15% (NB)",     "hst", "NB", 15.0,  True,  None),
    ("HST 15% (NL)",     "hst", "NL", 15.0,  True,  None),
    ("HST 15% (PE)",     "hst", "PE", 15.0,  True,  None),
    ("PST 7% (BC)",      "pst", "BC", 7.0,   False, None),
    ("PST 6% (SK)",      "pst", "SK", 6.0,   False, None),
    ("RST 7% (MB)",      "rst", "MB", 7.0,   False, None),
    ("QST 9.975% (QC)",  "qst", "QC", 9.975, True,  None),
]

#: Province -> the (federal_or_harmonized, provincial) regime it runs.
#: Each element is a (tax_type, province) key into SYSTEM_RATES.
#: A one-element tuple means a single-component regime (HST, or GST-only).
PROVINCE_REGIME: dict[str, tuple[tuple[TaxType, str | None], ...]] = {
    "ON": (("hst", "ON"),),
    "NS": (("hst", "NS"),),
    "NB": (("hst", "NB"),),
    "NL": (("hst", "NL"),),
    "PE": (("hst", "PE"),),
    "BC": (("gst", None), ("pst", "BC")),
    "SK": (("gst", None), ("pst", "SK")),
    "MB": (("gst", None), ("rst", "MB")),
    "QC": (("gst", None), ("qst", "QC")),
    "AB": (("gst", None),),
    "YT": (("gst", None),),
    "NT": (("gst", None),),
    "NU": (("gst", None),),
}

#: Types whose collected/paid amounts belong on the CRA GST34 return.
#: HST is remitted to CRA in full; GST always; PST/RST go to the province and
#: never appear on GST34. QST goes to Revenu Québec on its own return.
CRA_REMITTED_TYPES: frozenset[TaxType] = frozenset({"gst", "hst"})

SYSTEM_CREATED_BY = "system"

_TWO_PLACES = Decimal("0.01")


def _q(v) -> Decimal:
    return (v if isinstance(v, Decimal) else Decimal(str(v or 0))).quantize(_TWO_PLACES)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


async def seed_canadian_tax_rates(db: AsyncSession) -> int:
    """Idempotently insert the system rates. Returns how many were added.

    Match key is (tax_type, province, rate) among is_system rows, so re-running
    on every boot is safe and a future rate change adds a row instead of
    overwriting history.
    """
    existing = (
        await db.execute(
            select(TaxRate.tax_type, TaxRate.province, TaxRate.rate).where(
                TaxRate.is_system.is_(True)
            )
        )
    ).all()
    have = {(t, p, round(float(r), 3)) for t, p, r in existing}

    added = 0
    for name, tax_type, province, rate, recoverable, effective in SYSTEM_RATES:
        key = (tax_type, province, round(rate, 3))
        if key in have:
            continue
        db.add(TaxRate(
            name=name,
            rate=rate,
            description=f"Canadian {tax_type.upper()} — system rate",
            is_default=False,
            is_active=True,
            region=province or "CA",
            tax_type=tax_type,
            province=province,
            is_recoverable=recoverable,
            is_system=True,
            effective_from=effective,
            created_by=SYSTEM_CREATED_BY,
        ))
        added += 1
    if added:
        await db.commit()
    return added


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


async def _system_rate(db: AsyncSession, tax_type: TaxType, province: str | None) -> TaxRate | None:
    """Newest active system rate for a (type, province) key."""
    stmt = (
        select(TaxRate)
        .where(
            TaxRate.is_system.is_(True),
            TaxRate.is_active.is_(True),
            TaxRate.tax_type == tax_type,
        )
        .order_by(TaxRate.effective_from.desc().nullslast())
    )
    stmt = stmt.where(TaxRate.province == province) if province else stmt.where(TaxRate.province.is_(None))
    return (await db.execute(stmt)).scalars().first()


async def rates_for_province(
    db: AsyncSession, province: str | None
) -> tuple[TaxRate | None, TaxRate | None]:
    """(primary, secondary) system rates for a province code.

    ON -> (HST 13, None)   BC -> (GST 5, PST 7)   QC -> (GST 5, QST 9.975)
    AB -> (GST 5, None)    unknown -> (None, None)
    """
    if not province:
        return None, None
    regime = PROVINCE_REGIME.get(province.upper())
    if regime is None:
        logger.warning("canadian_tax: unknown province %r", province)
        return None, None
    primary = await _system_rate(db, *regime[0])
    secondary = await _system_rate(db, *regime[1]) if len(regime) > 1 else None
    return primary, secondary


def combined_rate(primary: TaxRate | None, secondary: TaxRate | None) -> float:
    """Total percentage applied to a pre-tax amount. BC = 5 + 7 = 12."""
    return float(primary.rate if primary else 0) + float(secondary.rate if secondary else 0)


def split_inclusive(
    total_amount, primary: TaxRate | None, secondary: TaxRate | None
) -> tuple[Decimal, Decimal, Decimal]:
    """Extract tax from a TAX-INCLUSIVE total.

    Returns (gst_hst_amount, pst_amount, total_tax). Both components are
    computed against the same pre-tax base (that is how BC/SK/MB/QC work —
    PST/QST is charged on the pre-GST price, not on top of GST).

    A single-component regime returns (tax, 0, tax).
    """
    total = _q(total_amount)
    rate_total = Decimal(str(combined_rate(primary, secondary)))
    if rate_total <= 0 or total == 0:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

    pre_tax = total / (Decimal("1") + rate_total / Decimal("100"))
    p_rate = Decimal(str(primary.rate)) if primary else Decimal("0")
    s_rate = Decimal(str(secondary.rate)) if secondary else Decimal("0")

    p_amt = _q(pre_tax * p_rate / Decimal("100"))
    s_amt = _q(pre_tax * s_rate / Decimal("100"))
    # Rounding drift lands on the total so gst+pst always equals recorded tax.
    total_tax = _q(total - _q(pre_tax))
    if p_amt + s_amt != total_tax:
        p_amt = _q(total_tax - s_amt)

    cra = p_amt if (primary and primary.tax_type in CRA_REMITTED_TYPES) else Decimal("0.00")
    prov = s_amt + (p_amt if (primary and primary.tax_type not in CRA_REMITTED_TYPES) else Decimal("0.00"))
    return cra, prov, total_tax


def split_exclusive(
    pre_tax_amount, primary: TaxRate | None, secondary: TaxRate | None
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute tax ON TOP OF a pre-tax amount (invoice lines).

    Returns (gst_hst_amount, pst_amount, total_tax).
    """
    base = _q(pre_tax_amount)
    p_amt = _q(base * Decimal(str(primary.rate)) / Decimal("100")) if primary else Decimal("0.00")
    s_amt = _q(base * Decimal(str(secondary.rate)) / Decimal("100")) if secondary else Decimal("0.00")
    cra = p_amt if (primary and primary.tax_type in CRA_REMITTED_TYPES) else Decimal("0.00")
    prov = s_amt + (p_amt if (primary and primary.tax_type not in CRA_REMITTED_TYPES) else Decimal("0.00"))
    return cra, prov, _q(p_amt + s_amt)
