"""De-provisioning: one audited action revokes a user's access everywhere.

Covers the deliverable's proof points: user deactivated, sessions revoked,
roles/features/MFA/passkeys cleared, telephony capabilities revoked, audit row
written, GitHub call made, manual checklist emitted, transfer path audited, and
the operator-only endpoint gate.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.audit.models import AuditLog
from app.auth.models import RefreshToken, Role, User
from app.auth.utils import hash_password
from app.auth.webauthn_models import WebAuthnCredential
from app.billing.models import TelephonyAccount
from app.platform_admin.deprovision import (
    build_manual_checklist,
    deprovision_user,
    transfer_user,
)
from app.integrations.github.client import remove_collaborator


def fake_settings(**over):
    base = dict(
        github_token="",
        github_repos="",
        github_api_base="https://api.github.com",
        telephony_exempt_emails="",
        super_admin_emails="",
    )
    base.update(over)
    return SimpleNamespace(**base)


async def make_user(db, *, email, role=Role.TEAM_MEMBER, **kw):
    u = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0],
        role=role,
        is_active=True,
        **kw,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def add_active_sessions(db, user, n=2):
    for _ in range(n):
        db.add(RefreshToken(
            user_id=user.id,
            token_hash=uuid.uuid4().hex,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=False,
        ))
    await db.commit()


async def add_telephony_account(db, user, **caps):
    acct = TelephonyAccount(
        tenant_key=str(user.id),
        owner_user_id=user.id,
        subaccount_sid=f"ACtest{uuid.uuid4().hex[:20]}",
        encrypted_auth_token="enc-token",
        status="active",
        **caps,
    )
    db.add(acct)
    await db.commit()
    return acct


# ---------------------------------------------------------------------------
# Core: deactivate + revoke sessions
# ---------------------------------------------------------------------------


async def test_deprovision_deactivates_and_revokes_all_sessions(db, admin_user):
    target = await make_user(db, email="leaver@test.com")
    await add_active_sessions(db, target, n=3)

    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user, settings=fake_settings()
    )

    await db.refresh(target)
    assert target.is_active is False
    # every refresh token is now revoked
    tokens = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == target.id)
    )).scalars().all()
    assert tokens and all(t.revoked for t in tokens)
    assert result["systems"]["sessions_revoked"] == 3
    assert result["systems"]["account_deactivated"] is True


# ---------------------------------------------------------------------------
# Roles / feature access / MFA / passkeys
# ---------------------------------------------------------------------------


async def test_deprovision_clears_role_features_mfa_and_passkeys(db, admin_user):
    target = await make_user(db, email="mfa@test.com", role=Role.MANAGER)
    target.feature_access_json = json.dumps({"cashbook": True, "invoices": True})
    target.mfa_enabled = True
    target.mfa_secret = "encrypted-totp-secret"
    target.mfa_recovery_codes = json.dumps(["a", "b"])
    db.add(WebAuthnCredential(
        user_id=target.id, credential_id=uuid.uuid4().hex,
        public_key=b"pk", sign_count=0, device_name="Phone",
    ))
    await db.commit()

    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user, settings=fake_settings()
    )

    await db.refresh(target)
    assert target.role == Role.VIEWER
    assert target.feature_access_json is None
    assert target.mfa_enabled is False
    assert target.mfa_secret is None
    assert target.mfa_recovery_codes is None
    passkeys = (await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == target.id)
    )).scalars().all()
    assert passkeys == []
    assert result["systems"]["role"] == {"from": "manager", "to": "viewer"}
    assert result["systems"]["passkeys_removed"] == 1
    assert result["systems"]["mfa_disabled"] is True


# ---------------------------------------------------------------------------
# Telephony capability grants
# ---------------------------------------------------------------------------


async def test_deprovision_revokes_telephony_capabilities(db, admin_user):
    target = await make_user(db, email="tel@test.com")
    await add_telephony_account(
        db, target,
        allow_sms=True, allow_voice_outbound=True, allow_number_purchase=True,
    )

    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user, settings=fake_settings()
    )

    acct = (await db.execute(
        select(TelephonyAccount).where(TelephonyAccount.tenant_key == str(target.id))
    )).scalar_one()
    assert acct.allow_sms is False
    assert acct.allow_voice_outbound is False
    assert acct.allow_number_purchase is False
    assert acct.capabilities_updated_by == admin_user.id
    assert set(result["systems"]["telephony"]["revoked"]) == {
        "allow_sms", "allow_voice_outbound", "allow_number_purchase",
    }


# ---------------------------------------------------------------------------
# Audit row
# ---------------------------------------------------------------------------


async def test_deprovision_writes_audit_row(db, admin_user):
    target = await make_user(db, email="audit@test.com")

    await deprovision_user(
        db, identifier=str(target.id), actor=admin_user,
        settings=fake_settings(), reason="left the company",
    )

    rows = (await db.execute(
        select(AuditLog).where(AuditLog.action == "user_deprovisioned")
    )).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_id == admin_user.id
    assert row.actor_email == admin_user.email
    assert row.resource_type == "user"
    assert row.resource_id == str(target.id)
    meta = json.loads(row.metadata_json)
    assert meta["target_email"] == "audit@test.com"
    assert meta["reason"] == "left the company"
    assert meta["systems_revoked"]["account_deactivated"] is True


# ---------------------------------------------------------------------------
# GitHub call
# ---------------------------------------------------------------------------


async def test_deprovision_calls_github_for_each_repo(db, admin_user, monkeypatch):
    target = await make_user(db, email="ghuser@test.com")
    calls = []

    async def fake_remove(token, repo, username, *, api_base):
        calls.append({"token": token, "repo": repo, "username": username})
        return {"repo": repo, "username": username, "status": "removed",
                "http_status": 204, "detail": None}

    monkeypatch.setattr("app.platform_admin.deprovision.remove_collaborator", fake_remove)

    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user,
        settings=fake_settings(github_token="ghp_secret", github_repos="acme/api, acme/web"),
        github_username="alice-gh",
    )

    assert len(calls) == 2
    assert {c["repo"] for c in calls} == {"acme/api", "acme/web"}
    assert all(c["username"] == "alice-gh" and c["token"] == "ghp_secret" for c in calls)
    assert result["systems"]["github"]["attempted"] is True
    assert all(r["status"] == "removed" for r in result["systems"]["github"]["repos"])


async def test_deprovision_github_skipped_when_unconfigured(db, admin_user):
    target = await make_user(db, email="nogh@test.com")
    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user,
        settings=fake_settings(),  # no token/repos
        github_username="alice-gh",
    )
    gh = result["systems"]["github"]
    assert gh["attempted"] is False
    # and the manual checklist tells the operator to do it by hand
    assert "GitHub" in result["manual_checklist"]


# ---------------------------------------------------------------------------
# Manual checklist
# ---------------------------------------------------------------------------


async def test_manual_checklist_is_dated_and_covers_manual_systems(db, admin_user):
    target = await make_user(db, email="chk@test.com")
    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user, settings=fake_settings()
    )
    cl = result["manual_checklist"]
    assert "chk@test.com" in cl
    assert "UTC" in cl  # dated header
    for needle in ["SSH", "DreamHost", "Twilio", "Plaid", "Stripe"]:
        assert needle in cl, f"checklist missing {needle}"


async def test_deprovision_flags_env_allowlists(db, admin_user):
    target = await make_user(db, email="privileged@test.com")
    result = await deprovision_user(
        db, identifier=str(target.id), actor=admin_user,
        settings=fake_settings(
            telephony_exempt_emails="privileged@test.com",
            super_admin_emails="privileged@test.com,other@test.com",
        ),
    )
    warnings = " ".join(result["warnings"])
    assert "TELEPHONY_EXEMPT_EMAILS" in warnings
    assert "SUPER_ADMIN_EMAILS" in warnings
    # warnings are also surfaced at the top of the checklist as required steps
    assert "TELEPHONY_EXEMPT_EMAILS" in result["manual_checklist"]


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


async def test_cannot_deprovision_self(db, admin_user):
    """The actor cannot target their own account (self-guard)."""
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await deprovision_user(
            db, identifier=str(admin_user.id), actor=admin_user, settings=fake_settings()
        )


async def test_cannot_deprovision_sole_operator(db, admin_user, team_member_user):
    """The last/sole operator cannot be de-provisioned — even by a DIFFERENT
    actor (defence in depth: the invariant holds at the service layer regardless
    of the actor gate, and independently of the self-guard)."""
    from app.core.exceptions import ValidationError

    # admin_user is the only operator; team_member_user is NOT an operator.
    with pytest.raises(ValidationError, match="last active operator"):
        await deprovision_user(
            db, identifier=str(admin_user.id), actor=team_member_user, settings=fake_settings()
        )
    # Nothing was revoked — the sole admin is untouched.
    await db.refresh(admin_user)
    assert admin_user.is_active is True
    assert admin_user.role == Role.ADMIN


async def test_sole_super_admin_email_cannot_be_deprovisioned(db, team_member_user):
    """A user who is an operator ONLY via SUPER_ADMIN_EMAILS still counts as the
    last operator and is protected."""
    from app.core.exceptions import ValidationError

    root = await make_user(db, email="root@ocidm.io", role=Role.VIEWER)  # not admin by role
    settings = fake_settings(super_admin_emails="root@ocidm.io")

    with pytest.raises(ValidationError, match="last active operator"):
        await deprovision_user(
            db, identifier=str(root.id), actor=team_member_user, settings=settings
        )
    await db.refresh(root)
    assert root.is_active is True


async def test_can_deprovision_admin_when_another_operator_remains(db, admin_user):
    """Guard is not over-broad: with two admins, one can be removed."""
    second = await make_user(db, email="second-admin@test.com", role=Role.ADMIN)

    result = await deprovision_user(
        db, identifier=str(second.id), actor=admin_user, settings=fake_settings()
    )
    await db.refresh(second)
    assert second.is_active is False
    assert result["systems"]["account_deactivated"] is True


async def test_cannot_transfer_last_operator_to_non_admin(db, admin_user, team_member_user):
    """Transfer/downgrade cannot strip the last operator's admin role either."""
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="last active operator"):
        await transfer_user(
            db, identifier=str(admin_user.id), actor=team_member_user,
            settings=fake_settings(), new_role=Role.VIEWER,
        )
    await db.refresh(admin_user)
    assert admin_user.role == Role.ADMIN  # unchanged


async def test_can_transfer_last_admin_when_they_stay_super_admin(db, admin_user, team_member_user):
    """Downgrading the last admin is allowed IF they remain an operator via
    SUPER_ADMIN_EMAILS (operator coverage is preserved)."""
    settings = fake_settings(super_admin_emails=admin_user.email)

    result = await transfer_user(
        db, identifier=str(admin_user.id), actor=team_member_user,
        settings=settings, new_role=Role.VIEWER,
    )
    await db.refresh(admin_user)
    assert admin_user.role == Role.VIEWER
    assert result["systems"]["role"] == {"from": "admin", "to": "viewer"}


# ---------------------------------------------------------------------------
# Transfer (role change) — same audited path
# ---------------------------------------------------------------------------


async def test_transfer_changes_role_revokes_caps_and_audits(db, admin_user):
    target = await make_user(db, email="promote@test.com", role=Role.TEAM_MEMBER)
    await add_active_sessions(db, target, n=2)
    await add_telephony_account(db, target, allow_sms=True)

    result = await transfer_user(
        db, identifier=str(target.id), actor=admin_user, settings=fake_settings(),
        new_role=Role.MANAGER, new_feature_access={"cashbook": True}, reason="promoted",
    )

    await db.refresh(target)
    assert target.role == Role.MANAGER
    assert target.is_active is True  # transfer does NOT deactivate
    assert json.loads(target.feature_access_json) == {"cashbook": True}
    # old sessions killed so new perms take effect on next login
    tokens = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == target.id)
    )).scalars().all()
    assert all(t.revoked for t in tokens)
    # capability grants cleared (least privilege on role change)
    acct = (await db.execute(
        select(TelephonyAccount).where(TelephonyAccount.tenant_key == str(target.id))
    )).scalar_one()
    assert acct.allow_sms is False

    rows = (await db.execute(
        select(AuditLog).where(AuditLog.action == "user_access_transferred")
    )).scalars().all()
    assert len(rows) == 1
    meta = json.loads(rows[0].metadata_json)
    assert meta["role"] == {"from": "team_member", "to": "manager"}
    assert result["action"] == "transfer"


# ---------------------------------------------------------------------------
# GitHub client unit tests (URL/headers, status handling)
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


class _FakeClient:
    def __init__(self, status):
        self.status = status
        self.calls = []

    async def request(self, method, url, headers=None):
        self.calls.append((method, url, headers))
        return _FakeResp(self.status)

    async def aclose(self):
        pass


async def test_github_remove_collaborator_builds_delete_and_reads_204():
    fc = _FakeClient(204)
    res = await remove_collaborator("ghp_x", "acme/api", "alice", client=fc)
    method, url, headers = fc.calls[0]
    assert method == "DELETE"
    assert url == "https://api.github.com/repos/acme/api/collaborators/alice"
    assert headers["Authorization"] == "Bearer ghp_x"
    assert res["status"] == "removed"
    assert res["http_status"] == 204


async def test_github_404_is_treated_as_already_removed():
    fc = _FakeClient(404)
    res = await remove_collaborator("ghp_x", "acme/api", "ghost", client=fc)
    assert res["status"] == "not_collaborator"


async def test_github_other_status_is_error():
    fc = _FakeClient(403)
    res = await remove_collaborator("ghp_x", "acme/api", "alice", client=fc)
    assert res["status"] == "error"


# ---------------------------------------------------------------------------
# Endpoint gate — operator only
# ---------------------------------------------------------------------------


async def test_deprovision_endpoint_requires_operator(client, db, admin_user, team_member_user):
    from tests.conftest import auth_header

    target = await make_user(db, email="endpoint-target@test.com")

    # A non-operator (team member) is refused.
    r = await client.post(
        f"/api/platform-admin/users/{target.id}/deprovision",
        json={}, headers=auth_header(team_member_user),
    )
    assert r.status_code == 403

    # An operator (admin) succeeds and the user is deactivated.
    r = await client.post(
        f"/api/platform-admin/users/{target.id}/deprovision",
        json={"reason": "left"}, headers=auth_header(admin_user),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["systems"]["account_deactivated"] is True

    # The endpoint committed in its own session — force this session to re-read
    # from the DB (populate_existing overwrites the identity-map copy inside the
    # awaited execute, so no lazy load fires on attribute access).
    fresh = (await db.execute(
        select(User).where(User.id == target.id).execution_options(populate_existing=True)
    )).scalar_one()
    assert fresh.is_active is False
