"""Pydantic schemas for news briefing system."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NewsPreferences(BaseModel):
    industries: list[str] = []
    topics: list[str] = []


class NewsArticleResponse(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    category: str
    fetched_at: datetime

    model_config = {"from_attributes": True}
