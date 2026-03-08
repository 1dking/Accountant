"""API endpoints for O-Brain Coach intelligence engine."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.coach import schemas, service
from app.dependencies import get_current_user, get_db

router = APIRouter()


# ── Meeting intelligence ─────────────────────────────────────────────────

@router.post("/meetings/{meeting_id}/analyze")
async def analyze_meeting(
    meeting_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Analyze a meeting transcript with AI and return intelligence."""
    intel = await service.analyze_meeting_transcript(db, meeting_id, current_user.id)
    if not intel:
        raise HTTPException(404, "Meeting transcript not found or analysis failed")
    return {"data": _intel_to_dict(intel)}


@router.get("/meetings/{meeting_id}/intelligence")
async def get_meeting_intelligence(
    meeting_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get existing intelligence for a meeting."""
    intel = await service.get_meeting_intelligence(db, meeting_id)
    if not intel:
        return {"data": None}
    return {"data": _intel_to_dict(intel)}


@router.post("/intelligence/{intel_id}/action-items")
async def toggle_action_item(
    intel_id: uuid.UUID,
    body: schemas.ActionItemToggle,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Toggle an action item as completed/uncompleted."""
    success = await service.toggle_action_item(db, intel_id, body.index, body.completed)
    if not success:
        raise HTTPException(404, "Intelligence record not found")
    return {"data": {"toggled": True}}


# ── Monthly reports ──────────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all monthly reports for the current user."""
    reports = await service.list_monthly_reports(db, current_user.id)
    return {
        "data": [
            {
                "id": str(r.id),
                "report_month": r.report_month,
                "health_score": r.health_score,
                "executive_summary": r.executive_summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
    }


@router.post("/reports/generate")
async def generate_report(
    body: schemas.GenerateReportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a monthly intelligence report (or return existing)."""
    report = await service.generate_monthly_report(db, current_user.id, body.month)
    if not report:
        raise HTTPException(500, "Failed to generate report")
    return {"data": _report_to_dict(report)}


@router.get("/reports/{month}")
async def get_report(
    month: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific monthly report."""
    report = await service.get_monthly_report(db, current_user.id, month)
    if not report:
        raise HTTPException(404, "Report not found")
    return {"data": _report_to_dict(report)}


# ── Deal outcomes ────────────────────────────────────────────────────────

@router.post("/deals/track/{proposal_id}")
async def track_deal(
    proposal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Track or update deal outcome from a proposal."""
    deal = await service.track_deal_outcome(db, proposal_id, current_user.id)
    if not deal:
        raise HTTPException(404, "Proposal not found")
    return {"data": {
        "id": str(deal.id),
        "outcome": deal.outcome,
        "deal_value": deal.deal_value,
        "cycle_days": deal.cycle_days,
    }}


@router.get("/deals/summary")
async def deals_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get aggregated win/loss deal summary."""
    summary = await service.get_deals_summary(db, current_user.id)
    return {"data": summary}


# ── Coaching nudges ──────────────────────────────────────────────────────

@router.get("/nudges")
async def list_nudges(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    unread_only: bool = Query(False),
):
    """List coaching nudges for the current user."""
    nudges = await service.list_nudges(db, current_user.id, unread_only)
    return {
        "data": [
            {
                "id": str(n.id),
                "nudge_type": n.nudge_type,
                "title": n.title,
                "message": n.message,
                "context": service._json_loads(n.context_json),
                "is_read": n.is_read,
                "is_acted_on": n.is_acted_on,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in nudges
        ]
    }


@router.post("/nudges/{nudge_id}/read")
async def mark_nudge_read(
    nudge_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a nudge as read."""
    success = await service.mark_nudge_read(db, nudge_id)
    if not success:
        raise HTTPException(404, "Nudge not found")
    return {"data": {"read": True}}


@router.post("/nudges/{nudge_id}/acted")
async def mark_nudge_acted(
    nudge_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a nudge as acted upon."""
    success = await service.mark_nudge_acted(db, nudge_id)
    if not success:
        raise HTTPException(404, "Nudge not found")
    return {"data": {"acted": True}}


# ── Helpers ──────────────────────────────────────────────────────────────

def _intel_to_dict(intel) -> dict:
    return {
        "id": str(intel.id),
        "meeting_id": str(intel.meeting_id),
        "summary_text": intel.summary_text,
        "topics": service._json_loads(intel.topics_json),
        "action_items": service._json_loads(intel.action_items_json),
        "decisions": service._json_loads(intel.decisions_json),
        "sentiment": service._json_loads(intel.sentiment_json),
        "talk_ratio": service._json_loads(intel.talk_ratio_json),
        "deal_signals": service._json_loads(intel.deal_signals_json),
        "risk_flags": service._json_loads(intel.risk_flags_json),
        "follow_ups": service._json_loads(intel.follow_ups_json),
        "suggestions": service._json_loads(intel.suggestions_json),
        "action_items_completed": service._json_loads(intel.action_items_completed_json),
        "created_at": intel.created_at.isoformat() if intel.created_at else None,
    }


def _report_to_dict(report) -> dict:
    return {
        "id": str(report.id),
        "report_month": report.report_month,
        "executive_summary": report.executive_summary,
        "whats_working": service._json_loads(report.whats_working_json),
        "watch_out": service._json_loads(report.watch_out_json),
        "revenue_insights": service._json_loads(report.revenue_insights_json),
        "meeting_patterns": service._json_loads(report.meeting_patterns_json),
        "recommendations": service._json_loads(report.recommendations_json),
        "trend_data": service._json_loads(report.trend_data_json),
        "win_loss": service._json_loads(report.win_loss_json),
        "health_score": report.health_score,
        "team_data": service._json_loads(report.team_data_json),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
