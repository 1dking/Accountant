"""Commit 19 — larger-meeting support: max_participants + recording_layout.

Covers:
  - MeetingCreate accepts max_participants and persists it
  - MeetingCreate accepts recording_layout='speaker' or 'grid'
  - InstantMeetingCreate accepts both fields too
  - Invalid recording_layout fails Pydantic validation (422-ish at API)
  - LiveKit start_room_recording layout kwarg falls through to Egress
  - Unknown layout passed to start_room_recording falls back to 'speaker'
    (defensive — LiveKit rejects unknown values)
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.meetings import livekit_egress, service
from app.meetings.schemas import InstantMeetingCreate, MeetingCreate
from tests.conftest import TEST_SETTINGS


@pytest_asyncio.fixture
async def settings_lk():
    return TEST_SETTINGS.model_copy(update={
        "livekit_url": "wss://x.com",
        "livekit_api_key": "k",
        "livekit_api_secret": "thirtytwobytekeyforsigningttests",
        "r2_access_key_id": "r2k",
        "r2_secret_access_key": "r2s",
        "r2_bucket_name": "test-recordings",
        "r2_endpoint": "https://test.r2.cloudflarestorage.com",
    })


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(), email="host@example.com",
        hashed_password=hash_password("x"),
        full_name="Host", role=Role.ACCOUNTANT,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# Schema acceptance
# ---------------------------------------------------------------------------


def test_meeting_create_accepts_capacity_fields():
    data = MeetingCreate(
        title="big workshop",
        scheduled_start=datetime.now(timezone.utc),
        max_participants=20,
        recording_layout="grid",
    )
    assert data.max_participants == 20
    assert data.recording_layout == "grid"


def test_meeting_create_recording_layout_rejects_unknown():
    """Pydantic regex pattern catches typos before they reach LiveKit."""
    with pytest.raises(Exception):
        MeetingCreate(
            title="x",
            scheduled_start=datetime.now(timezone.utc),
            recording_layout="single_speaker",  # not a valid value
        )


def test_instant_meeting_create_accepts_capacity_fields():
    data = InstantMeetingCreate(
        max_participants=15, recording_layout="grid",
    )
    assert data.max_participants == 15
    assert data.recording_layout == "grid"


# ---------------------------------------------------------------------------
# Persistence — create_meeting writes the columns
# ---------------------------------------------------------------------------


async def test_create_meeting_persists_capacity_fields(
    db: AsyncSession, host: User, settings_lk,
):
    data = MeetingCreate(
        title="workshop",
        scheduled_start=datetime.now(timezone.utc),
        max_participants=40,
        recording_layout="grid",
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    assert meeting.max_participants == 40
    assert meeting.recording_layout == "grid"


async def test_create_meeting_defaults_capacity_when_omitted(
    db: AsyncSession, host: User, settings_lk,
):
    data = MeetingCreate(
        title="default",
        scheduled_start=datetime.now(timezone.utc),
        create_calendar_event=False,
    )
    meeting = await service.create_meeting(db, host, data, settings_lk)
    assert meeting.max_participants is None
    assert meeting.recording_layout is None


# ---------------------------------------------------------------------------
# Egress receives layout kwarg
# ---------------------------------------------------------------------------


async def test_egress_layout_kwarg_passes_through(
    settings_lk, monkeypatch,
):
    """start_room_recording must thread the layout kwarg into the
    RoomCompositeEgressRequest. Stubs the LiveKitAPI client so we
    don't actually hit Cloud."""
    captured: dict = {}

    class _FakeEgressClient:
        api_key = "k"
        api_secret = "s"
        async def start_room_composite_egress(self, req):
            captured["layout"] = req.layout
            captured["room"] = req.room_name
            class _R:
                egress_id = "EG_x"
            return _R()

    class _FakeApi:
        def __init__(self, **k): self.egress = _FakeEgressClient()
        async def aclose(self): pass

    monkeypatch.setattr(livekit_egress, "_get_lkapi", lambda s: _FakeApi())

    egress_id, _path = await livekit_egress.start_room_recording(
        "room-x", settings_lk, layout="grid",
    )
    assert egress_id == "EG_x"
    assert captured["layout"] == "grid"


async def test_egress_layout_unknown_value_falls_back_to_speaker(
    settings_lk, monkeypatch,
):
    """Defensive — an unexpected layout string (typo, future template
    we haven't shipped backend support for) falls back to 'speaker'
    rather than letting LiveKit reject the entire egress."""
    captured: dict = {}

    class _FakeEgressClient:
        api_key = "k"
        api_secret = "s"
        async def start_room_composite_egress(self, req):
            captured["layout"] = req.layout
            class _R:
                egress_id = "EG_y"
            return _R()

    class _FakeApi:
        def __init__(self, **k): self.egress = _FakeEgressClient()
        async def aclose(self): pass

    monkeypatch.setattr(livekit_egress, "_get_lkapi", lambda s: _FakeApi())

    await livekit_egress.start_room_recording(
        "room-y", settings_lk, layout="weird_future_value",
    )
    assert captured["layout"] == "speaker"
