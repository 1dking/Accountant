"""Export services for cashbook data (CSV)."""

import csv
import io
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.cashbook import service
from app.cashbook.schemas import CashbookEntryFilter
from app.core.pagination import PaginationParams


async def export_cashbook_csv(
    db: AsyncSession,
    filters: CashbookEntryFilter,
) -> bytes:
    """Export filtered cashbook entries as a CSV file."""
    pagination = PaginationParams(page=1, page_size=50000)
    entries, _ = await service.list_entries(db, filters, pagination)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Date",
        "Description",
        "Type",
        "Category",
        "Amount",
        "Tax",
        "Balance",
        "Notes",
    ])

    for entry in entries:
        cat_name = ""
        if isinstance(entry, dict):
            cat = entry.get("category")
            if cat and hasattr(cat, "name"):
                cat_name = cat.name
            elif cat and isinstance(cat, dict):
                cat_name = cat.get("name", "")
            entry_date = entry["date"]
            date_str = (
                entry_date.isoformat()
                if isinstance(entry_date, date)
                else str(entry_date)
            )
            entry_type = entry["entry_type"]
            type_str = (
                entry_type.value
                if hasattr(entry_type, "value")
                else str(entry_type)
            )
            writer.writerow([
                date_str,
                entry["description"],
                type_str,
                cat_name or "Uncategorized",
                f"{entry['total_amount']:.2f}",
                f"{entry['tax_amount']:.2f}" if entry.get("tax_amount") else "",
                f"{entry['bank_balance']:.2f}" if entry.get("bank_balance") is not None else "",
                entry.get("notes") or "",
            ])

    return output.getvalue().encode("utf-8")
