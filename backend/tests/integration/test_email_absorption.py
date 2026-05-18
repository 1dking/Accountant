"""Email absorption pipeline (Session E) — unit-level tests against
the absorber's pure logic + idempotency contract.

Strategy: we don't run the full Gmail-API integration end-to-end —
that needs OAuth tokens + a live mailbox. Instead we stub
``_get_gmail_service`` with a fake that returns a scripted list of
messages, exercising the matcher + idempotency + opt-out + summary-
failure branches deterministically.

The 6 named tests in the Session E spec:
  1. test_email_absorption_idempotent
  2. test_email_match_by_from_header
  3. test_email_match_by_to_header
  4. test_email_no_match_skipped
  5. test_email_absorption_disabled_per_contact
  6. test_email_summary_failure_persists_row
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.communication.models import AbsorbedEmail, EmailAbsorptionRun
from app.contacts.models import Contact, ContactMemory, ContactType
from app.core.encryption import init_encryption_service
from app.integrations.gmail.models import GmailAccount
from tests.conftest import TEST_SETTINGS

init_encryption_service(TEST_SETTINGS.fernet_key)


# ---------------------------------------------------------------------------
# Gmail fake — minimal surface the absorber needs.
# ---------------------------------------------------------------------------


def _b64url(s: str) -> str:
    """Gmail-format body data: urlsafe-base64 WITH padding. The
    extractor uses ``base64.urlsafe_b64decode`` which requires padding."""
    import base64
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")


def _make_message(
    *,
    msg_id: str,
    thread_id: str = "thread-1",
    from_addr: str,
    to_addr: str,
    subject: str = "Re: pricing",
    body: str = "Sounds good, let's lock in $1,500 for Q3.",
    snippet: str | None = None,
    sent_at_iso: str = "Wed, 14 May 2026 10:30:00 -0400",
) -> dict:
    return {
        "id": msg_id,
        "threadId": thread_id,
        "snippet": snippet or body[:120],
        "internalDate": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
        "payload": {
            "headers": [
                {"name": "From", "value": from_addr},
                {"name": "To", "value": to_addr},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": sent_at_iso},
            ],
            "mimeType": "text/plain",
            "body": {"data": _b64url(body)},
        },
    }


class _FakeMessages:
    def __init__(self, messages: list[dict]):
        self._messages = {m["id"]: m for m in messages}

    def list(self, *, userId, q, maxResults, pageToken=None):
        class _Req:
            def __init__(inner_self, payload):
                inner_self._payload = payload

            def execute(inner_self):
                return inner_self._payload

        refs = [{"id": mid} for mid in self._messages]
        return _Req({"messages": refs})

    def get(self, *, userId, id, format):
        class _Req:
            def __init__(inner_self, payload):
                inner_self._payload = payload

            def execute(inner_self):
                return inner_self._payload

        return _Req(self._messages[id])


class _FakeUsers:
    def __init__(self, messages: list[dict]):
        self._messages = _FakeMessages(messages)

    def messages(self):
        return self._messages


class _FakeGmailService:
    def __init__(self, messages: list[dict]):
        self._users = _FakeUsers(messages)

    def users(self):
        return self._users


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def user_with_gmail(db: AsyncSession, admin_user: User) -> User:
    from app.core.encryption import get_encryption_service

    db.add(GmailAccount(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        email="me@example.com",
        encrypted_access_token=get_encryption_service().encrypt("dummy-access"),
        encrypted_refresh_token=get_encryption_service().encrypt("dummy-refresh"),
        scopes="https://www.googleapis.com/auth/gmail.readonly",
        is_active=True,
    ))
    await db.commit()
    return admin_user


@pytest_asyncio.fixture
async def sarah_contact(db: AsyncSession, admin_user: User) -> Contact:
    c = Contact(
        id=uuid.uuid4(),
        type=ContactType.CLIENT,
        company_name="Acme Corp",
        contact_name="Sarah Adams",
        email="sarah@acme.com",
        country="US",
        created_by=admin_user.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _run_absorption(
    db: AsyncSession,
    user_id: uuid.UUID,
    messages: list[dict],
    monkeypatch,
    summarize_returns: dict | None = None,
    summarize_raises: Exception | None = None,
    lookback_days: int = 7,
) -> EmailAbsorptionRun:
    """Drive absorb_user_emails_task with a stubbed Gmail service and
    a stubbed Claude summarizer. Returns the run row after the worker
    completes."""
    from app.communication import email_absorber

    fake_service = _FakeGmailService(messages)

    async def _stub_service(*_args, **_kwargs):
        return fake_service

    async def _stub_summary(**_kwargs):
        if summarize_raises is not None:
            raise summarize_raises
        return summarize_returns or {
            "summary": "Discussed pricing and timeline.",
            "commitments": "Lock in $1,500 for Q3.",
            "cares_about": "Predictable monthly cost.",
            "talking_points": "Confirm Q3 timeline.",
        }

    monkeypatch.setattr(email_absorber, "_get_gmail_service", _stub_service)
    monkeypatch.setattr(email_absorber, "_summarize_email", _stub_summary)

    # Create the run row through the same code path the endpoint uses.
    run = EmailAbsorptionRun(
        id=uuid.uuid4(),
        user_id=user_id,
        status="queued",
        lookback_days=lookback_days,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Use a session_factory factory that yields the same engine the
    # test fixture is using, so the worker reads/writes the test DB.
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db.bind, expire_on_commit=False)

    await email_absorber.absorb_user_emails_task(
        run_id=run.id,
        user_id=user_id,
        session_factory=factory,
    )

    # Re-fetch run from a fresh session so we see the worker's writes.
    async with factory() as fresh:
        return (await fresh.execute(
            select(EmailAbsorptionRun).where(EmailAbsorptionRun.id == run.id)
        )).scalar_one()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.high
async def test_email_absorption_idempotent(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """Running absorb twice with the same message yields exactly one
    AbsorbedEmail + one ContactMemory row. The (user_id,
    gmail_message_id) unique index is the anchor."""
    msg = _make_message(
        msg_id="msg-1",
        from_addr="Sarah Adams <sarah@acme.com>",
        to_addr="me@example.com",
    )

    run1 = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run1.status == "complete"
    assert run1.absorbed == 1

    run2 = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run2.status == "complete"
    # Second run sees the message already absorbed → skipped.
    assert run2.absorbed == 0
    assert run2.skipped >= 1

    rows = await db.execute(
        select(AbsorbedEmail).where(AbsorbedEmail.gmail_message_id == "msg-1")
    )
    assert len(list(rows.scalars().all())) == 1

    mem_rows = await db.execute(
        select(ContactMemory).where(
            ContactMemory.contact_id == sarah_contact.id,
            ContactMemory.source_type == "email",
        )
    )
    assert len(list(mem_rows.scalars().all())) == 1


@pytest.mark.high
async def test_email_match_by_from_header(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """Inbound: From=contact.email → direction='inbound', absorbed."""
    msg = _make_message(
        msg_id="inbound-1",
        from_addr='"Sarah" <sarah@acme.com>',
        to_addr="me@example.com",
    )
    run = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run.status == "complete"
    assert run.absorbed == 1

    row = (await db.execute(
        select(AbsorbedEmail).where(AbsorbedEmail.gmail_message_id == "inbound-1")
    )).scalar_one()
    assert row.direction == "inbound"
    assert row.contact_id == sarah_contact.id


@pytest.mark.high
async def test_email_match_by_to_header(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """Outbound: From=user.email AND To=contact.email →
    direction='outbound', absorbed."""
    msg = _make_message(
        msg_id="outbound-1",
        from_addr="Me <me@example.com>",
        to_addr="Sarah <sarah@acme.com>",
    )
    run = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run.status == "complete"
    assert run.absorbed == 1

    row = (await db.execute(
        select(AbsorbedEmail).where(AbsorbedEmail.gmail_message_id == "outbound-1")
    )).scalar_one()
    assert row.direction == "outbound"
    assert row.contact_id == sarah_contact.id


@pytest.mark.high
async def test_email_no_match_skipped(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """Message between two strangers (neither From nor To matches a
    CRM contact OR the user's own email) is NOT absorbed."""
    msg = _make_message(
        msg_id="stranger-1",
        from_addr="bob@unknown.test",
        to_addr="alice@stranger.test",
    )
    run = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run.status == "complete"
    assert run.scanned == 1
    assert run.matched == 0
    assert run.absorbed == 0

    rows = await db.execute(
        select(AbsorbedEmail).where(AbsorbedEmail.gmail_message_id == "stranger-1")
    )
    assert rows.scalar_one_or_none() is None


@pytest.mark.high
async def test_email_absorption_disabled_per_contact(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """Contact with email_absorption_enabled=False is excluded from
    the matcher even though their email matches a header."""
    sarah_contact.email_absorption_enabled = False
    await db.commit()

    msg = _make_message(
        msg_id="opted-out-1",
        from_addr="sarah@acme.com",
        to_addr="me@example.com",
    )
    run = await _run_absorption(db, user_with_gmail.id, [msg], monkeypatch)
    assert run.status == "complete"
    assert run.matched == 0
    assert run.absorbed == 0


@pytest.mark.high
async def test_email_summary_failure_persists_row(
    db: AsyncSession,
    user_with_gmail: User,
    sarah_contact: Contact,
    monkeypatch,
):
    """When Claude summarization raises, the absorbed_emails row still
    persists (with body_summary=NULL and no memory_id). The whole
    batch must not be lost because of one bad summary."""
    msg = _make_message(
        msg_id="summary-fails-1",
        from_addr="sarah@acme.com",
        to_addr="me@example.com",
    )
    run = await _run_absorption(
        db, user_with_gmail.id, [msg], monkeypatch,
        summarize_raises=RuntimeError("anthropic 503"),
    )
    assert run.status == "complete"
    # Note: when summarization fails, the per-message coroutine still
    # persists the absorbed_emails row → counts as "absorbed".
    assert run.absorbed == 1

    row = (await db.execute(
        select(AbsorbedEmail).where(AbsorbedEmail.gmail_message_id == "summary-fails-1")
    )).scalar_one()
    assert row.body_summary is None
    assert row.memory_id is None

    # No ContactMemory row was created since summarization failed.
    mem_rows = await db.execute(
        select(ContactMemory).where(
            ContactMemory.contact_id == sarah_contact.id,
            ContactMemory.source_type == "email",
        )
    )
    assert list(mem_rows.scalars().all()) == []
