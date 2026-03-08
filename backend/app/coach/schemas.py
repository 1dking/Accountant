"""Pydantic schemas for O-Brain Coach."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MeetingIntelligenceResponse(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    summary_text: Optional[str] = None
    topics: list = []
    action_items: list = []
    decisions: list = []
    sentiment: dict = {}
    talk_ratio: list = []
    deal_signals: list = []
    risk_flags: list = []
    follow_ups: list = []
    suggestions: list = []
    action_items_completed: list = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MonthlyReportResponse(BaseModel):
    id: uuid.UUID
    report_month: str
    executive_summary: Optional[str] = None
    whats_working: list = []
    watch_out: list = []
    revenue_insights: dict = {}
    meeting_patterns: dict = {}
    recommendations: list = []
    trend_data: dict = {}
    win_loss: dict = {}
    health_score: int = 50
    team_data: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class MonthlyReportListItem(BaseModel):
    id: uuid.UUID
    report_month: str
    health_score: int
    executive_summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DealOutcomeResponse(BaseModel):
    id: uuid.UUID
    contact_id: Optional[uuid.UUID] = None
    proposal_id: Optional[uuid.UUID] = None
    outcome: str
    deal_value: float
    cycle_days: int
    meetings_count: int
    emails_count: int
    win_factors: list = []
    loss_factors: list = []
    analysis: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class CoachingNudgeResponse(BaseModel):
    id: uuid.UUID
    nudge_type: str
    title: str
    message: str
    context: dict = {}
    is_read: bool
    is_acted_on: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionItemToggle(BaseModel):
    index: int
    completed: bool


class AnalyzeMeetingRequest(BaseModel):
    meeting_id: uuid.UUID


class GenerateReportRequest(BaseModel):
    month: Optional[str] = None  # YYYY-MM, defaults to previous month


class DealsSummary(BaseModel):
    total_deals: int = 0
    wins: int = 0
    losses: int = 0
    pending: int = 0
    win_rate: float = 0.0
    avg_deal_value: float = 0.0
    avg_cycle_days: int = 0
    total_revenue: float = 0.0
    top_win_factors: list = []
    top_loss_factors: list = []
    deals: list = []
