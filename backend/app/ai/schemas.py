"""Pydantic schemas for the AI module."""


import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None


class ReceiptExtractionResult(BaseModel):
    vendor_name: str | None = None
    vendor_address: str | None = None
    date: str | None = None
    currency: str = "USD"
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    tax_rate: Decimal | None = None
    total_amount: Decimal | None = None
    tip_amount: Decimal | None = None
    payment_method: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    category: str | None = None
    receipt_number: str | None = None
    full_text: str = ""


class AIProcessResponse(BaseModel):
    document_id: uuid.UUID
    extraction: ReceiptExtractionResult
    processing_time_ms: int


class AIExtractionStatus(BaseModel):
    document_id: uuid.UUID
    has_extraction: bool
    extraction: ReceiptExtractionResult | None = None


class HelpChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=5000)


class HelpChatRequest(BaseModel):
    messages: list[HelpChatMessage] = Field(..., min_length=1, max_length=20)
