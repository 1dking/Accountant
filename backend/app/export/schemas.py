
from typing import Optional

from datetime import date

from pydantic import BaseModel


class ExportRequest(BaseModel):
    format: str = "csv"  # "csv" | "iif"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    include: str = "all"  # "expenses" | "income" | "invoices" | "all"
