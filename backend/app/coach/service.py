"""O-Brain Coach intelligence services — meeting analysis, monthly reports, win/loss, nudges."""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import anthropic
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.models import CoachingNudge, DealOutcome, MeetingIntelligence, MonthlyReport
from app.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()


def _json_loads(val: str | None) -> list | dict:
    if not val:
        return []
    try:
        return json.loads(val)
    except Exception:
        return []


# ── Meeting intelligence ─────────────────────────────────────────────────

MEETING_ANALYSIS_PROMPT = """Analyze this meeting transcript. Extract the following as a JSON object:

{
  "summary": "2-3 sentence summary of the meeting",
  "topics": ["topic1", "topic2", ...],
  "action_items": [{"task": "description", "owner": "person name", "deadline": "if mentioned or null"}],
  "decisions": ["decision 1", "decision 2", ...],
  "sentiment": {"overall": "positive|neutral|negative", "participants": {"name": "sentiment"}},
  "talk_ratio": [{"name": "person", "percentage": 45}],
  "deal_signals": [{"type": "buying_signal|objection|competitor_mention", "text": "relevant quote", "positive": true}],
  "risk_flags": [{"flag": "description of concern", "severity": "low|medium|high"}],
  "follow_ups": [{"action": "what to do", "priority": "high|medium|low", "suggested_date": "if applicable or null"}],
  "suggestions": ["O-Brain Coach suggestion 1", "suggestion 2"]
}

Return ONLY valid JSON, no markdown or explanation.

TRANSCRIPT:
"""


async def analyze_meeting_transcript(
    db: AsyncSession, meeting_id: uuid.UUID, user_id: uuid.UUID
) -> MeetingIntelligence | None:
    """Analyze a meeting transcript using Claude and store results."""
    from app.brain.models import MeetingTranscript

    # Check if already analyzed
    existing = await db.execute(
        select(MeetingIntelligence).where(MeetingIntelligence.meeting_id == meeting_id)
    )
    if existing.scalar_one_or_none():
        return existing.scalar_one_or_none()

    # Re-query to avoid stale result
    existing_check = await db.execute(
        select(MeetingIntelligence).where(MeetingIntelligence.meeting_id == meeting_id)
    )
    intel = existing_check.scalar_one_or_none()
    if intel:
        return intel

    # Get transcript
    result = await db.execute(
        select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript or not transcript.full_text:
        return None

    # Truncate very long transcripts to avoid excessive cost
    text = transcript.full_text[:30000]

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": MEETING_ANALYSIS_PROMPT + text}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        if raw.startswith("json"):
            raw = raw[4:]

        data = json.loads(raw.strip())
    except Exception as e:
        logger.exception("Failed to analyze meeting %s: %s", meeting_id, e)
        return None

    intel = MeetingIntelligence(
        meeting_id=meeting_id,
        user_id=user_id,
        summary_text=data.get("summary", ""),
        topics_json=json.dumps(data.get("topics", [])),
        action_items_json=json.dumps(data.get("action_items", [])),
        decisions_json=json.dumps(data.get("decisions", [])),
        sentiment_json=json.dumps(data.get("sentiment", {})),
        talk_ratio_json=json.dumps(data.get("talk_ratio", [])),
        deal_signals_json=json.dumps(data.get("deal_signals", [])),
        risk_flags_json=json.dumps(data.get("risk_flags", [])),
        follow_ups_json=json.dumps(data.get("follow_ups", [])),
        suggestions_json=json.dumps(data.get("suggestions", [])),
        action_items_completed_json=json.dumps([]),
    )
    db.add(intel)
    await db.commit()
    await db.refresh(intel)

    # Create coaching nudge for follow-up
    follow_ups = data.get("follow_ups", [])
    if follow_ups:
        from app.meetings.models import Meeting
        meeting_result = await db.execute(select(Meeting.title).where(Meeting.id == meeting_id))
        meeting_title = meeting_result.scalar_one_or_none() or "Meeting"
        nudge = CoachingNudge(
            user_id=user_id,
            nudge_type="meeting_followup",
            title=f"Follow up on: {meeting_title}",
            message=f"Your meeting just ended. {len(follow_ups)} follow-up actions were identified. "
                    f"Top priority: {follow_ups[0].get('action', 'Review action items')}",
            context_json=json.dumps({"meeting_id": str(meeting_id), "follow_ups": follow_ups}),
        )
        db.add(nudge)
        await db.commit()

    return intel


async def get_meeting_intelligence(
    db: AsyncSession, meeting_id: uuid.UUID
) -> MeetingIntelligence | None:
    result = await db.execute(
        select(MeetingIntelligence).where(MeetingIntelligence.meeting_id == meeting_id)
    )
    return result.scalar_one_or_none()


async def toggle_action_item(
    db: AsyncSession, intel_id: uuid.UUID, index: int, completed: bool
) -> bool:
    result = await db.execute(
        select(MeetingIntelligence).where(MeetingIntelligence.id == intel_id)
    )
    intel = result.scalar_one_or_none()
    if not intel:
        return False

    completed_list = _json_loads(intel.action_items_completed_json)
    if not isinstance(completed_list, list):
        completed_list = []

    if completed and index not in completed_list:
        completed_list.append(index)
    elif not completed and index in completed_list:
        completed_list.remove(index)

    intel.action_items_completed_json = json.dumps(completed_list)
    await db.commit()
    return True


# ── Monthly report generation ────────────────────────────────────────────

MONTHLY_REPORT_PROMPT = """You are O-Brain Coach, a business intelligence analyst. Given the following data for the month of {month}:

{data_summary}

Generate a Monthly Intelligence Report as a JSON object:

{{
  "executive_summary": "3-4 sentence overview of the month",
  "whats_working": [
    {{"title": "insight title", "detail": "explanation with specific data", "metric": "key number"}}
  ],
  "watch_out": [
    {{"title": "concern title", "detail": "explanation with specific data", "severity": "low|medium|high"}}
  ],
  "revenue_insights": {{
    "total_income": number,
    "total_expenses": number,
    "net": number,
    "trend": "up|down|flat",
    "top_sources": ["source1", "source2"],
    "pipeline_value": number,
    "insight": "one sentence revenue insight"
  }},
  "meeting_patterns": {{
    "total_meetings": number,
    "avg_duration_minutes": number,
    "action_completion_rate": number,
    "insight": "one sentence about meeting productivity"
  }},
  "recommendations": [
    {{"action": "specific recommendation", "priority": "high|medium|low", "category": "revenue|operations|growth"}}
  ],
  "win_loss": {{
    "wins": number,
    "losses": number,
    "win_rate": number,
    "avg_deal_value": number,
    "avg_cycle_days": number,
    "top_win_patterns": ["pattern1"],
    "top_loss_patterns": ["pattern1"],
    "insight": "one sentence about deal patterns"
  }},
  "health_score": number_1_to_100,
  "trend_data": {{
    "months": ["label1", "label2"],
    "revenue": [number1, number2],
    "contacts": [number1, number2],
    "proposals_won": [number1, number2],
    "health_scores": [number1, number2]
  }}
}}

Return ONLY valid JSON. Be specific with data — use the actual numbers provided.
3-5 recommendations max. Health score based on: revenue trend, proposal win rate, meeting productivity, client growth, and overall momentum.
"""


async def gather_monthly_data(db: AsyncSession, user_id: uuid.UUID, month: str) -> dict:
    """Gather all platform data for a given month (YYYY-MM format)."""
    from app.invoicing.models import Invoice
    from app.accounting.models import Expense
    from app.proposals.models import Proposal
    from app.contacts.models import Contact
    from app.meetings.models import Meeting
    from app.documents.models import Document
    from app.brain.models import BrainConversation, MeetingTranscript
    from app.collaboration.models import ActivityLog

    year, mo = int(month[:4]), int(month[5:7])
    start = datetime(year, mo, 1, tzinfo=timezone.utc)
    if mo == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, mo + 1, 1, tzinfo=timezone.utc)

    # Revenue
    total_income = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.created_at >= start, Invoice.created_at < end)
    )).scalar() or 0)

    paid_income = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.created_at >= start, Invoice.created_at < end,
               Invoice.status == "paid")
    )).scalar() or 0)

    invoices_created = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.created_at >= start, Invoice.created_at < end)
    )).scalar() or 0

    # Expenses
    total_expenses = float((await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.created_at >= start, Expense.created_at < end)
    )).scalar() or 0)

    # Proposals
    proposals_sent = (await db.execute(
        select(func.count(Proposal.id))
        .where(Proposal.sent_at >= start, Proposal.sent_at < end)
    )).scalar() or 0

    proposals_won = (await db.execute(
        select(func.count(Proposal.id))
        .where(Proposal.signed_at >= start, Proposal.signed_at < end)
    )).scalar() or 0

    proposals_lost = (await db.execute(
        select(func.count(Proposal.id))
        .where(Proposal.status == "declined",
               Proposal.updated_at >= start, Proposal.updated_at < end)
    )).scalar() or 0

    pipeline_value = float((await db.execute(
        select(func.coalesce(func.sum(Proposal.value), 0))
        .where(Proposal.status.in_(["sent", "viewed", "waiting_signature"]))
    )).scalar() or 0)

    # Contacts
    new_contacts = (await db.execute(
        select(func.count(Contact.id))
        .where(Contact.created_at >= start, Contact.created_at < end)
    )).scalar() or 0

    # Meetings
    meeting_count = (await db.execute(
        select(func.count(Meeting.id))
        .where(Meeting.scheduled_start >= start, Meeting.scheduled_start < end)
    )).scalar() or 0

    # O-Brain conversations
    conversation_count = (await db.execute(
        select(func.count(BrainConversation.id))
        .where(BrainConversation.created_at >= start, BrainConversation.created_at < end)
    )).scalar() or 0

    # Meeting intelligence summaries
    intel_rows = (await db.execute(
        select(MeetingIntelligence.summary_text, MeetingIntelligence.topics_json)
        .join(Meeting, MeetingIntelligence.meeting_id == Meeting.id)
        .where(Meeting.scheduled_start >= start, Meeting.scheduled_start < end)
        .limit(20)
    )).all()
    meeting_summaries = [
        f"- {row.summary_text}" for row in intel_rows if row.summary_text
    ]

    # Activities count
    activity_count = (await db.execute(
        select(func.count(ActivityLog.id))
        .where(ActivityLog.created_at >= start, ActivityLog.created_at < end)
    )).scalar() or 0

    # Historical data for trend (last 6 months)
    trend_months = []
    trend_revenue = []
    trend_contacts = []
    trend_proposals_won = []
    trend_health_scores = []

    for i in range(5, -1, -1):
        t_year, t_mo = year, mo - i
        while t_mo <= 0:
            t_mo += 12
            t_year -= 1
        t_label = f"{t_year}-{t_mo:02d}"
        t_start = datetime(t_year, t_mo, 1, tzinfo=timezone.utc)
        t_end_mo = t_mo + 1
        t_end_year = t_year
        if t_end_mo > 12:
            t_end_mo = 1
            t_end_year += 1
        t_end = datetime(t_end_year, t_end_mo, 1, tzinfo=timezone.utc)

        rev = float((await db.execute(
            select(func.coalesce(func.sum(Invoice.total), 0))
            .where(Invoice.created_at >= t_start, Invoice.created_at < t_end)
        )).scalar() or 0)

        ct = (await db.execute(
            select(func.count(Contact.id))
            .where(Contact.created_at >= t_start, Contact.created_at < t_end)
        )).scalar() or 0

        pw = (await db.execute(
            select(func.count(Proposal.id))
            .where(Proposal.signed_at >= t_start, Proposal.signed_at < t_end)
        )).scalar() or 0

        # Get historical health score if exists
        hs_result = await db.execute(
            select(MonthlyReport.health_score)
            .where(MonthlyReport.report_month == t_label)
            .limit(1)
        )
        hs = hs_result.scalar_one_or_none() or 0

        trend_months.append(t_label)
        trend_revenue.append(rev)
        trend_contacts.append(ct)
        trend_proposals_won.append(pw)
        trend_health_scores.append(hs)

    acceptance_rate = round(proposals_won / max(proposals_sent, 1) * 100, 1)

    return {
        "month": month,
        "total_income": total_income,
        "paid_income": paid_income,
        "total_expenses": total_expenses,
        "net": total_income - total_expenses,
        "invoices_created": invoices_created,
        "proposals_sent": proposals_sent,
        "proposals_won": proposals_won,
        "proposals_lost": proposals_lost,
        "acceptance_rate": acceptance_rate,
        "pipeline_value": pipeline_value,
        "new_contacts": new_contacts,
        "meeting_count": meeting_count,
        "conversation_count": conversation_count,
        "activity_count": activity_count,
        "meeting_summaries": "\n".join(meeting_summaries[:10]),
        "trend_months": trend_months,
        "trend_revenue": trend_revenue,
        "trend_contacts": trend_contacts,
        "trend_proposals_won": trend_proposals_won,
        "trend_health_scores": trend_health_scores,
    }


async def generate_monthly_report(
    db: AsyncSession, user_id: uuid.UUID, month: str | None = None
) -> MonthlyReport | None:
    """Generate or retrieve monthly intelligence report."""
    if not month:
        now = datetime.now(timezone.utc)
        prev = now.replace(day=1) - timedelta(days=1)
        month = prev.strftime("%Y-%m")

    # Check existing
    existing = await db.execute(
        select(MonthlyReport)
        .where(MonthlyReport.user_id == user_id, MonthlyReport.report_month == month)
    )
    report = existing.scalar_one_or_none()
    if report:
        return report

    # Gather data
    data = await gather_monthly_data(db, user_id, month)

    data_summary = f"""Meetings: {data['meeting_count']} meetings
Revenue: ${data['total_income']:,.2f} income, ${data['total_expenses']:,.2f} expenses, ${data['net']:,.2f} net
Proposals: {data['proposals_sent']} sent, {data['proposals_won']} accepted ({data['acceptance_rate']}% rate), {data['proposals_lost']} rejected
Invoices: {data['invoices_created']} created, ${data['paid_income']:,.2f} paid
Pipeline value: ${data['pipeline_value']:,.2f}
New contacts: {data['new_contacts']}
O-Brain conversations: {data['conversation_count']}
Total platform activities: {data['activity_count']}

Meeting summaries from this month:
{data['meeting_summaries'] or 'No meeting intelligence available yet.'}

6-month revenue trend: {data['trend_revenue']}
6-month new contacts trend: {data['trend_contacts']}
6-month proposals won trend: {data['trend_proposals_won']}"""

    prompt = MONTHLY_REPORT_PROMPT.format(month=month, data_summary=data_summary)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        if raw.startswith("json"):
            raw = raw[4:]

        result = json.loads(raw.strip())
    except Exception as e:
        logger.exception("Failed to generate monthly report for %s: %s", month, e)
        return None

    report = MonthlyReport(
        user_id=user_id,
        report_month=month,
        executive_summary=result.get("executive_summary", ""),
        whats_working_json=json.dumps(result.get("whats_working", [])),
        watch_out_json=json.dumps(result.get("watch_out", [])),
        revenue_insights_json=json.dumps(result.get("revenue_insights", {})),
        meeting_patterns_json=json.dumps(result.get("meeting_patterns", {})),
        recommendations_json=json.dumps(result.get("recommendations", [])),
        trend_data_json=json.dumps(result.get("trend_data", data.get("trend_data", {}))),
        win_loss_json=json.dumps(result.get("win_loss", {})),
        health_score=int(result.get("health_score", 50)),
        raw_data_json=json.dumps(data),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def list_monthly_reports(db: AsyncSession, user_id: uuid.UUID) -> list[MonthlyReport]:
    result = await db.execute(
        select(MonthlyReport)
        .where(MonthlyReport.user_id == user_id)
        .order_by(MonthlyReport.report_month.desc())
    )
    return list(result.scalars().all())


async def get_monthly_report(
    db: AsyncSession, user_id: uuid.UUID, month: str
) -> MonthlyReport | None:
    result = await db.execute(
        select(MonthlyReport)
        .where(MonthlyReport.user_id == user_id, MonthlyReport.report_month == month)
    )
    return result.scalar_one_or_none()


# ── Deal outcome tracking ────────────────────────────────────────────────

async def track_deal_outcome(
    db: AsyncSession, proposal_id: uuid.UUID, user_id: uuid.UUID
) -> DealOutcome | None:
    """Create or update a deal outcome when a proposal status changes."""
    from app.proposals.models import Proposal
    from app.meetings.models import Meeting

    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        return None

    # Determine outcome
    if proposal.status.value in ("signed", "paid"):
        outcome = "win"
    elif proposal.status.value == "declined":
        outcome = "loss"
    else:
        outcome = "pending"

    # Calculate cycle days
    cycle_days = 0
    if proposal.sent_at:
        end_date = proposal.signed_at or proposal.updated_at or datetime.now(timezone.utc)
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        sent = proposal.sent_at
        if hasattr(sent, 'tzinfo') and sent.tzinfo is None:
            sent = sent.replace(tzinfo=timezone.utc)
        cycle_days = (end_date - sent).days

    # Count related meetings
    meetings_count = 0
    if proposal.contact_id:
        meetings_count = (await db.execute(
            select(func.count(Meeting.id))
            .where(Meeting.contact_id == proposal.contact_id)
        )).scalar() or 0

    # Check existing
    existing = await db.execute(
        select(DealOutcome).where(DealOutcome.proposal_id == proposal_id)
    )
    deal = existing.scalar_one_or_none()

    if deal:
        deal.outcome = outcome
        deal.deal_value = float(proposal.value)
        deal.cycle_days = cycle_days
        deal.meetings_count = meetings_count
    else:
        deal = DealOutcome(
            user_id=user_id,
            contact_id=proposal.contact_id,
            proposal_id=proposal_id,
            outcome=outcome,
            deal_value=float(proposal.value),
            cycle_days=cycle_days,
            meetings_count=meetings_count,
        )
        db.add(deal)

    await db.commit()
    await db.refresh(deal)
    return deal


async def get_deals_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get aggregated win/loss stats."""
    deals = (await db.execute(
        select(DealOutcome)
        .where(DealOutcome.user_id == user_id)
        .order_by(DealOutcome.created_at.desc())
    )).scalars().all()

    wins = [d for d in deals if d.outcome == "win"]
    losses = [d for d in deals if d.outcome == "loss"]
    pending = [d for d in deals if d.outcome == "pending"]

    total = len(wins) + len(losses)
    win_rate = round(len(wins) / max(total, 1) * 100, 1)
    avg_value = round(sum(d.deal_value for d in deals) / max(len(deals), 1), 2)
    avg_cycle = round(sum(d.cycle_days for d in deals if d.cycle_days > 0) / max(len([d for d in deals if d.cycle_days > 0]), 1))
    total_revenue = sum(d.deal_value for d in wins)

    # Aggregate factors
    all_win_factors = []
    all_loss_factors = []
    for d in wins:
        all_win_factors.extend(_json_loads(d.win_factors_json))
    for d in losses:
        all_loss_factors.extend(_json_loads(d.loss_factors_json))

    return {
        "total_deals": len(deals),
        "wins": len(wins),
        "losses": len(losses),
        "pending": len(pending),
        "win_rate": win_rate,
        "avg_deal_value": avg_value,
        "avg_cycle_days": avg_cycle,
        "total_revenue": total_revenue,
        "top_win_factors": all_win_factors[:5],
        "top_loss_factors": all_loss_factors[:5],
        "deals": [
            {
                "id": str(d.id),
                "outcome": d.outcome,
                "deal_value": d.deal_value,
                "cycle_days": d.cycle_days,
                "meetings_count": d.meetings_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deals[:50]
        ],
    }


# ── Coaching nudges ──────────────────────────────────────────────────────

async def list_nudges(
    db: AsyncSession, user_id: uuid.UUID, unread_only: bool = False
) -> list[CoachingNudge]:
    stmt = (
        select(CoachingNudge)
        .where(CoachingNudge.user_id == user_id)
        .order_by(CoachingNudge.created_at.desc())
        .limit(50)
    )
    if unread_only:
        stmt = stmt.where(CoachingNudge.is_read == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_nudge_read(db: AsyncSession, nudge_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(CoachingNudge).where(CoachingNudge.id == nudge_id)
    )
    nudge = result.scalar_one_or_none()
    if not nudge:
        return False
    nudge.is_read = True
    await db.commit()
    return True


async def mark_nudge_acted(db: AsyncSession, nudge_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(CoachingNudge).where(CoachingNudge.id == nudge_id)
    )
    nudge = result.scalar_one_or_none()
    if not nudge:
        return False
    nudge.is_acted_on = True
    nudge.is_read = True
    await db.commit()
    return True


# ── Scheduled jobs ───────────────────────────────────────────────────────

async def check_coaching_nudges(session_factory) -> int:
    """Hourly job: check for conditions that should trigger coaching nudges."""
    from app.proposals.models import Proposal
    from app.invoicing.models import Invoice
    from app.auth.models import User

    count = 0
    async with session_factory() as db:
        now = datetime.now(timezone.utc)

        # Get all active admin/team users (Coach candidates)
        users = (await db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )).scalars().all()

        for user in users:
            # 1. Proposals sent 3+ days ago with no response
            three_days_ago = now - timedelta(days=3)
            stale_proposals = (await db.execute(
                select(Proposal)
                .where(
                    Proposal.created_by == user.id,
                    Proposal.status == "sent",
                    Proposal.sent_at <= three_days_ago,
                    Proposal.sent_at >= three_days_ago - timedelta(days=1),  # Only trigger once
                )
            )).scalars().all()

            for prop in stale_proposals:
                # Check if nudge already exists
                existing = await db.execute(
                    select(CoachingNudge)
                    .where(
                        CoachingNudge.user_id == user.id,
                        CoachingNudge.nudge_type == "proposal_followup",
                        CoachingNudge.context_json.contains(str(prop.id)),
                    )
                )
                if not existing.scalar_one_or_none():
                    nudge = CoachingNudge(
                        user_id=user.id,
                        nudge_type="proposal_followup",
                        title=f"Follow up on proposal: {prop.title}",
                        message=f"Your proposal \"{prop.title}\" (${float(prop.value):,.2f}) was sent "
                                f"3 days ago with no response. Deals that get a follow-up within 3-5 days "
                                f"have higher close rates. Consider sending a gentle check-in.",
                        context_json=json.dumps({"proposal_id": str(prop.id)}),
                    )
                    db.add(nudge)
                    count += 1

            # 2. Overdue invoices (14+ days)
            fourteen_days_ago = now - timedelta(days=14)
            overdue_invoices = (await db.execute(
                select(Invoice)
                .where(
                    Invoice.created_by == user.id,
                    Invoice.status == "overdue",
                    Invoice.due_date <= fourteen_days_ago.date() if hasattr(Invoice, 'due_date') else Invoice.created_at <= fourteen_days_ago,
                )
                .limit(5)
            )).scalars().all()

            for inv in overdue_invoices:
                existing = await db.execute(
                    select(CoachingNudge)
                    .where(
                        CoachingNudge.user_id == user.id,
                        CoachingNudge.nudge_type == "overdue_invoice",
                        CoachingNudge.context_json.contains(str(inv.id)),
                    )
                )
                if not existing.scalar_one_or_none():
                    nudge = CoachingNudge(
                        user_id=user.id,
                        nudge_type="overdue_invoice",
                        title=f"Overdue invoice: #{getattr(inv, 'invoice_number', 'N/A')}",
                        message=f"Invoice #{getattr(inv, 'invoice_number', 'N/A')} for "
                                f"${float(inv.total):,.2f} is now 14+ days overdue. "
                                f"Consider sending a payment reminder.",
                        context_json=json.dumps({"invoice_id": str(inv.id)}),
                    )
                    db.add(nudge)
                    count += 1

        if count:
            await db.commit()

    return count


async def run_monthly_reports(session_factory) -> int:
    """Monthly job: generate reports for all users."""
    from app.auth.models import User

    count = 0
    async with session_factory() as db:
        users = (await db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )).scalars().all()

        for user in users:
            try:
                report = await generate_monthly_report(db, user.id)
                if report:
                    count += 1
            except Exception as e:
                logger.exception("Failed monthly report for user %s: %s", user.id, e)

    return count
