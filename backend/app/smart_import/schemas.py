"""Smart Import Pydantic schemas."""

from pydantic import BaseModel, ConfigDict


class SmartImportResponse(BaseModel):
    id: str
    original_filename: str
    mime_type: str
    file_size: int
    status: str
    document_type: str | None = None
    ai_summary: str | None = None
    error_message: str | None = None
    processing_time_ms: int | None = None
    item_count: int = 0
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class SmartImportItemResponse(BaseModel):
    id: str
    status: str
    entry_type: str
    date: str | None = None
    description: str
    amount: float
    tax_amount: float | None = None
    category_suggestion: str | None = None
    confidence: float = 0.0
    is_duplicate: bool = False
    duplicate_entry_id: str | None = None
    cashbook_entry_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SmartImportDetailResponse(SmartImportResponse):
    items: list[SmartImportItemResponse] = []


class ImportItemUpdate(BaseModel):
    status: str | None = None
    entry_type: str | None = None
    date: str | None = None
    description: str | None = None
    amount: float | None = None
    tax_amount: float | None = None
    category_suggestion: str | None = None


class ImportConfirmRequest(BaseModel):
    account_id: str
    item_ids: list[str] | None = None  # None = all approved items
