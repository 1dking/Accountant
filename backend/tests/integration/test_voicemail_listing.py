"""Voicemail tab data.

Voicemails and calls share the `call_logs` table, split by `kind`. The list
endpoint had no `kind` filter, so the dialer's Voicemail tab had no way to ask
for just voicemails — which is part of why it shipped as a "coming in Phase B"
placeholder.
"""
import uuid

import pytest

from app.auth.models import User
from app.communication.models import CallLog
from app.communication.service import list_call_logs
from tests.conftest import auth_header


async def _seed(db, admin_user: User):
    db.add_all(
        [
            CallLog(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                direction="inbound",
                from_number="+15551110000",
                to_number="+15559990000",
                status="completed",
                kind="call",
            ),
            CallLog(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                direction="inbound",
                from_number="+15552220000",
                to_number="+15559990000",
                status="completed",
                kind="voicemail",
                recording_url="https://api.twilio.com/rec/abc.mp3",
                recording_duration_seconds=17,
                voicemail_transcript="Hi, calling about the quote.",
                voicemail_transcript_status="completed",
            ),
        ]
    )
    await db.commit()


@pytest.mark.high
async def test_kind_filter_returns_only_voicemails(db, admin_user: User):
    await _seed(db, admin_user)

    voicemails, total = await list_call_logs(db, kind="voicemail")

    assert total == 1
    assert len(voicemails) == 1
    assert voicemails[0].kind == "voicemail"
    assert voicemails[0].voicemail_transcript == "Hi, calling about the quote."
    assert voicemails[0].recording_url


@pytest.mark.high
async def test_no_kind_filter_returns_everything(db, admin_user: User):
    await _seed(db, admin_user)

    rows, total = await list_call_logs(db)

    assert total == 2, "an unfiltered list must still show calls and voicemails"


@pytest.mark.high
async def test_voicemail_endpoint_exposes_transcript_and_recording(
    client, db, admin_user: User
):
    await _seed(db, admin_user)

    resp = await client.get(
        "/api/communication/calls?kind=voicemail", headers=auth_header(admin_user)
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["kind"] == "voicemail"
    assert data[0]["voicemail_transcript"] == "Hi, calling about the quote."
    assert data[0]["recording_duration_seconds"] == 17


@pytest.mark.high
async def test_bad_kind_is_rejected(client, admin_user: User):
    """The filter is constrained — a typo shouldn't silently return everything."""
    resp = await client.get(
        "/api/communication/calls?kind=bogus", headers=auth_header(admin_user)
    )
    assert resp.status_code == 422
