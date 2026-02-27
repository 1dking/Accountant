"""Pydantic schemas for the AI module."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    total: float | None = None


class ReceiptExtractionResult(BaseModel):
    vendor_name: str | None = None
    vendor_address: str | None = None
    date: str | None = None
    currency: str = "USD"
    subtotal: float | None = None
    tax_amount: float | None = None
    tax_rate: float | None = None
    total_amount: float | None = None
    tip_amount: float | None = None
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
