
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreatePaymentLinkRequest(BaseModel):
    invoice_id: uuid.UUID


class PaymentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    checkout_session_id: str | None = None
    payment_intent_id: str | None = None
    payment_url: str
    amount: float
    currency: str
    status: str
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime


class StripeConfigResponse(BaseModel):
    is_configured: bool
    publishable_key: str | None = None


class CreateSubscriptionRequest(BaseModel):
    contact_id: uuid.UUID
    name: str
    amount: float
    currency: str = "USD"
    interval: str  # monthly | quarterly | yearly


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    stripe_subscription_id: str
    stripe_customer_id: str
    name: str
    amount: float
    currency: str
    interval: str
    status: str
    current_period_end: datetime | None = None
    created_at: datetime
