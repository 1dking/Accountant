"""Proposal follow-up rules must actually fire.

`process_pending_follow_ups` had zero call sites and was not registered with
the scheduler, so the whole feature was inert: users could create rules in the
UI that would never run. And the function itself only incremented `send_count`
without sending — so had it ever run, it would have reported "3 follow-ups
sent" for mail that never left.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth.models import User
from app.core.encryption import init_encryption_service
from app.proposals.models import (
    FollowUpRule,
    Proposal,
    ProposalActivity,
    ProposalRecipient,
    ProposalStatus,
)
from app.proposals.service import process_pending_follow_ups
from tests.conftest import TEST_SETTINGS

init_encryption_service(TEST_SETTINGS.fernet_key)


@pytest_asyncio.fixture
async def smtp_default(db, admin_user):
    from app.core.encryption import get_encryption_service
    from app.email.models import SmtpConfig

    cfg = SmtpConfig(
        id=uuid.uuid4(),
        name="Default",
        host="smtp.example.com",
        port=587,
        username="noreply@example.com",
        encrypted_password=get_encryption_service().encrypt("dummy"),
        from_email="noreply@example.com",
        from_name="Accountant Test",
        use_tls=True,
        is_default=True,
        created_by=admin_user.id,
    )
    db.add(cfg)
    await db.commit()
    return cfg


@pytest_asyncio.fixture
async def sent_proposal(db, admin_user, sample_contact) -> Proposal:
    """A proposal sent 72h ago and still unsigned — i.e. overdue for a nudge."""
    proposal = Proposal(
        id=uuid.uuid4(),
        proposal_number="PRO-0001",
        contact_id=sample_contact.id,
        title="Website rebuild",
        content_json="[]",
        value=5000,
        currency="USD",
        status=ProposalStatus.SENT,
        sent_at=datetime.now(timezone.utc) - timedelta(hours=72),
        public_token=uuid.uuid4().hex,
        created_by=admin_user.id,
    )
    db.add(proposal)
    await db.flush()
    db.add(
        ProposalRecipient(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            email="signer@test.com",
            name="Sam Signer",
            role="signer",
            signing_token=uuid.uuid4().hex,
        )
    )
    await db.commit()
    return proposal


async def _make_rule(db, admin_user, proposal, **overrides) -> FollowUpRule:
    rule = FollowUpRule(
        id=uuid.uuid4(),
        resource_type="proposal",
        resource_id=proposal.id,
        trigger_event="not_signed",
        delay_hours=overrides.get("delay_hours", 48),
        channel=overrides.get("channel", "email"),
        message_template=overrides.get("message_template"),
        is_active=True,
        created_by=admin_user.id,
    )
    db.add(rule)
    await db.commit()
    return rule


@pytest.mark.critical
async def test_due_follow_up_sends_email(
    db, admin_user: User, sent_proposal: Proposal, smtp_default, monkeypatch
):
    sent: list[dict] = []

    async def _stub_send(smtp_config, to, subject, html_body, attachments=None):
        sent.append({"to": to, "body": html_body})

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    rule = await _make_rule(db, admin_user, sent_proposal)

    count = await process_pending_follow_ups(db, TEST_SETTINGS)

    assert count == 1
    assert len(sent) == 1, "the follow-up must actually be emailed"
    assert sent[0]["to"] == "signer@test.com"

    await db.refresh(rule)
    assert rule.send_count == 1
    assert rule.last_sent_at is not None


@pytest.mark.critical
async def test_failed_follow_up_does_not_increment_send_count(
    db, admin_user: User, sent_proposal: Proposal, smtp_default, monkeypatch
):
    """The original bug: send_count went up whether or not anything was sent."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("smtp refused")

    monkeypatch.setattr("app.email.service.send_email", _boom)

    rule = await _make_rule(db, admin_user, sent_proposal)

    count = await process_pending_follow_ups(db, TEST_SETTINGS)

    assert count == 0
    await db.refresh(rule)
    assert rule.send_count == 0, "must not claim a send that failed"
    assert rule.last_sent_at is None

    activities = (
        await db.execute(
            select(ProposalActivity).where(
                ProposalActivity.proposal_id == sent_proposal.id
            )
        )
    ).scalars().all()
    actions = {a.action for a in activities}
    assert "follow_up_failed" in actions
    assert "follow_up_sent" not in actions


@pytest.mark.high
async def test_follow_up_not_sent_before_delay_elapses(
    db, admin_user: User, sent_proposal: Proposal, smtp_default, monkeypatch
):
    sent: list = []

    async def _stub_send(*args, **kwargs):
        sent.append(1)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    # Sent 72h ago, but this rule doesn't want a nudge until 96h.
    await _make_rule(db, admin_user, sent_proposal, delay_hours=96)

    count = await process_pending_follow_ups(db, TEST_SETTINGS)

    assert count == 0
    assert sent == []


@pytest.mark.high
async def test_signed_proposal_is_not_followed_up(
    db, admin_user: User, sent_proposal: Proposal, smtp_default, monkeypatch
):
    """Nagging someone who already signed is the most embarrassing failure mode."""
    sent: list = []

    async def _stub_send(*args, **kwargs):
        sent.append(1)

    monkeypatch.setattr("app.email.service.send_email", _stub_send)

    sent_proposal.status = ProposalStatus.SIGNED
    await db.commit()

    await _make_rule(db, admin_user, sent_proposal)

    count = await process_pending_follow_ups(db, TEST_SETTINGS)

    assert count == 0
    assert sent == [], "must not chase a signed proposal"


@pytest.mark.high
def test_follow_up_job_is_registered_with_the_scheduler():
    """The function existed and worked-ish, but nothing ever called it. Guard
    that regression directly."""
    import inspect

    from app.core import scheduler as scheduler_module

    source = inspect.getsource(scheduler_module.setup_scheduler)
    assert "_process_proposal_follow_ups" in source, (
        "follow-up job must be registered in setup_scheduler, or the whole "
        "feature is inert"
    )
