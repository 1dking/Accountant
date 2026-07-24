from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan_key: str
    period: str = Field(default="monthly", pattern="^(monthly|annual)$")


class SubscriptionResponse(BaseModel):
    plan_key: str
    status: str
    billing_period: Optional[str] = None
    current_period_end: Optional[datetime] = None
    has_stripe_customer: bool = False
