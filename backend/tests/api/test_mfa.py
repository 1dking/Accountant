"""MFA (TOTP) — pure primitives + full enroll/login/gate flow."""

import pytest

from app.auth import mfa
from app.core.encryption import init_encryption_service
from tests.conftest import TEST_SETTINGS, auth_header

# MFA secret is stored encrypted — the enroll endpoint needs the service.
init_encryption_service(TEST_SETTINGS.fernet_key)

PASSWORD = "TestPass123!"


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    from app.auth import router as auth_router

    auth_router._login_attempts.clear()
    yield


# ---------------------------------------------------------------------------
# Pure TOTP + recovery-code primitives
# ---------------------------------------------------------------------------

def test_totp_roundtrip_and_window():
    at = 1_700_000_000
    secret = mfa.generate_secret()
    code = mfa.totp_now(secret, at=at)
    assert mfa.verify_totp(secret, code, at=at)
    # Within the +/-1 step tolerance
    assert mfa.verify_totp(secret, code, at=at + 29)
    # Far outside the window
    assert not mfa.verify_totp(secret, code, at=at + 120)
    # Garbage
    assert not mfa.verify_totp(secret, "000000", at=at) or code == "000000"


def test_recovery_codes_single_use():
    plain, hashed = mfa.generate_recovery_codes(5)
    assert len(plain) == 5 and len(hashed) == 5
    remaining = mfa.consume_recovery_code(plain[0], hashed)
    assert remaining is not None and len(remaining) == 4
    # Same code can't be used twice
    assert mfa.consume_recovery_code(plain[0], remaining) is None


def test_provisioning_uri_shape():
    uri = mfa.provisioning_uri("ABC234", "user@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "secret=ABC234" in uri


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enroll_and_confirm(client, team_member_user):
    hdr = auth_header(team_member_user)

    r = await client.post("/api/auth/mfa/enroll", headers=hdr)
    assert r.status_code == 200, r.text
    secret = r.json()["data"]["secret"]
    assert r.json()["data"]["otpauth_uri"].startswith("otpauth://")

    # Status still shows disabled until confirmed
    s = await client.get("/api/auth/mfa/status", headers=hdr)
    assert s.json()["data"]["mfa_enabled"] is False

    # Wrong code is rejected
    bad = await client.post("/api/auth/mfa/enroll/confirm", headers=hdr, json={"code": "000000"})
    assert bad.status_code in (400, 422)

    code = mfa.totp_now(secret)
    ok = await client.post("/api/auth/mfa/enroll/confirm", headers=hdr, json={"code": code})
    assert ok.status_code == 200, ok.text
    recovery = ok.json()["data"]["recovery_codes"]
    assert len(recovery) == mfa.RECOVERY_CODE_COUNT

    s2 = await client.get("/api/auth/mfa/status", headers=hdr)
    assert s2.json()["data"]["mfa_enabled"] is True
    assert s2.json()["data"]["recovery_codes_remaining"] == mfa.RECOVERY_CODE_COUNT


# ---------------------------------------------------------------------------
# Two-step login
# ---------------------------------------------------------------------------

async def _enroll(client, user) -> tuple[str, list[str]]:
    hdr = auth_header(user)
    secret = (await client.post("/api/auth/mfa/enroll", headers=hdr)).json()["data"]["secret"]
    recovery = (
        await client.post(
            "/api/auth/mfa/enroll/confirm", headers=hdr, json={"code": mfa.totp_now(secret)}
        )
    ).json()["data"]["recovery_codes"]
    return secret, recovery


@pytest.mark.asyncio
async def test_login_requires_second_factor(client, team_member_user):
    secret, _ = await _enroll(client, team_member_user)

    # Password login now returns a challenge, not tokens.
    r = await client.post(
        "/api/auth/login", json={"email": team_member_user.email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body.get("mfa_required") is True
    assert "access_token" not in body
    mfa_token = body["mfa_token"]

    # Wrong TOTP fails
    bad = await client.post(
        "/api/auth/mfa/login", json={"mfa_token": mfa_token, "code": "000000"}
    )
    assert bad.status_code in (400, 422)

    # Correct TOTP yields real tokens
    good = await client.post(
        "/api/auth/mfa/login", json={"mfa_token": mfa_token, "code": mfa.totp_now(secret)}
    )
    assert good.status_code == 200, good.text
    assert good.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_recovery_code_login_is_single_use(client, team_member_user):
    _, recovery = await _enroll(client, team_member_user)
    code = recovery[0]

    tok1 = (
        await client.post(
            "/api/auth/login", json={"email": team_member_user.email, "password": PASSWORD}
        )
    ).json()["data"]["mfa_token"]
    r1 = await client.post("/api/auth/mfa/login", json={"mfa_token": tok1, "code": code})
    assert r1.status_code == 200, r1.text

    # The same recovery code can't be used again
    tok2 = (
        await client.post(
            "/api/auth/login", json={"email": team_member_user.email, "password": PASSWORD}
        )
    ).json()["data"]["mfa_token"]
    r2 = await client.post("/api/auth/mfa/login", json={"mfa_token": tok2, "code": code})
    assert r2.status_code in (400, 422)


@pytest.mark.asyncio
async def test_disable_requires_valid_code(client, team_member_user):
    secret, _ = await _enroll(client, team_member_user)
    hdr = auth_header(team_member_user)

    bad = await client.post("/api/auth/mfa/disable", headers=hdr, json={"code": "000000"})
    assert bad.status_code in (400, 422)

    ok = await client.post(
        "/api/auth/mfa/disable", headers=hdr, json={"code": mfa.totp_now(secret)}
    )
    assert ok.status_code == 200, ok.text
    s = await client.get("/api/auth/mfa/status", headers=hdr)
    assert s.json()["data"]["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_non_mfa_user_logs_in_normally(client, team_member_user):
    """Regression: users without MFA still get tokens directly."""
    r = await client.post(
        "/api/auth/login", json={"email": team_member_user.email, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["access_token"]
