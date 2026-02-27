from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ExportRequest(BaseModel):
    format: str = "csv"  # "csv" | "iif"
    date_from: date | None = None
    date_to: date | None = None
    include: str = "all"  # "expenses" | "income" | "invoices" | "all"
