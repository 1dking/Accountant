#!/usr/bin/env python
"""Capture current Twilio geo permissions — READ ONLY. The rollback artifact.

Run this BEFORE hardening geo permissions. It records, for the parent account and
every subaccount we own:

  * voice dialing permissions per country (which are enabled);
  * SMS/messaging country permissions per country, where the SDK exposes them;
  * messaging services and whether SMS Pumping Protection is on.

The JSON snapshot it writes is what you restore from if hardening blocks a
destination you actually use — see telephony_geo_restore.py.

This script never writes to Twilio. There is deliberately no --apply flag; the
apply step is a separate script so a capture can never mutate anything.

Usage (from backend/, on the box that has the Twilio credentials):
  .venv/bin/python scripts/telephony_geo_capture.py
  .venv/bin/python scripts/telephony_geo_capture.py --out /path/snapshot.json
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402


def _voice_permissions(client) -> dict:
    """Which countries voice may dial. Returns {} + an error note on failure."""
    try:
        out = {}
        for c in client.voice.dialing_permissions.countries.list(limit=1000):
            iso = getattr(c, "iso_code", None)
            if not iso:
                continue
            out[iso] = {
                "low_risk_numbers_enabled": getattr(c, "low_risk_numbers_enabled", None),
                "high_risk_special_numbers_enabled": getattr(
                    c, "high_risk_special_numbers_enabled", None
                ),
                "high_risk_tollfraud_numbers_enabled": getattr(
                    c, "high_risk_tollfraud_numbers_enabled", None
                ),
            }
        return out
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _sms_permissions(client) -> dict:
    """SMS country permissions. Not exposed by every twilio-python version."""
    try:
        svc = getattr(getattr(client, "messaging", None), "v1", None)
        perms = getattr(svc, "country_permissions", None) if svc else None
        if perms is None:
            return {"__unsupported__": "this twilio SDK has no messaging country_permissions"}
        out = {}
        for c in perms.list(limit=1000):
            iso = getattr(c, "iso_code", None)
            if iso:
                out[iso] = {
                    "low_risk_numbers_enabled": getattr(c, "low_risk_numbers_enabled", None)
                }
        return out
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _messaging_services(client) -> list:
    try:
        return [
            {
                "sid": s.sid,
                "friendly_name": getattr(s, "friendly_name", None),
                "sms_pumping_risk_check_enabled": getattr(
                    s, "sms_pumping_risk_check_enabled", None
                ),
            }
            for s in client.messaging.v1.services.list(limit=100)
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"__error__": f"{type(exc).__name__}: {str(exc)[:200]}"}]


def _numbers(client) -> list:
    try:
        return [
            {
                "phone_number": n.phone_number,
                "friendly_name": getattr(n, "friendly_name", None),
                "sid": n.sid,
            }
            for n in client.incoming_phone_numbers.list(limit=100)
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"__error__": f"{type(exc).__name__}: {str(exc)[:200]}"}]


def _snapshot(client, label: str) -> dict:
    return {
        "label": label,
        "voice_dialing_permissions": _voice_permissions(client),
        "sms_country_permissions": _sms_permissions(client),
        "messaging_services": _messaging_services(client),
        "incoming_phone_numbers": _numbers(client),
    }


def _summarize(snap: dict) -> None:
    voice = snap.get("voice_dialing_permissions", {})
    sms = snap.get("sms_country_permissions", {})
    print(f"\n--- {snap['label']} ---")

    if "__error__" in voice:
        print(f"  voice: ERROR {voice['__error__']}")
    else:
        enabled = sorted(
            iso for iso, v in voice.items() if v.get("low_risk_numbers_enabled")
        )
        print(f"  voice countries listed: {len(voice)}")
        print(f"  voice ENABLED ({len(enabled)}): {', '.join(enabled) if enabled else 'none'}")

    if "__unsupported__" in sms:
        print(f"  sms:   {sms['__unsupported__']}")
    elif "__error__" in sms:
        print(f"  sms:   ERROR {sms['__error__']}")
    else:
        enabled = sorted(
            iso for iso, v in sms.items() if v.get("low_risk_numbers_enabled")
        )
        print(f"  sms countries listed: {len(sms)}")
        print(f"  sms ENABLED ({len(enabled)}): {', '.join(enabled) if enabled else 'none'}")

    svcs = snap.get("messaging_services", [])
    if svcs and "__error__" in svcs[0]:
        print(f"  messaging services: ERROR {svcs[0]['__error__']}")
    else:
        print(f"  messaging services: {len(svcs)}")
        for s in svcs:
            print(
                f"    - {s.get('friendly_name')} ({s.get('sid')}) "
                f"pumping_protection={s.get('sms_pumping_risk_check_enabled')}"
            )

    nums = snap.get("incoming_phone_numbers", [])
    if nums and "__error__" in nums[0]:
        print(f"  numbers: ERROR {nums[0]['__error__']}")
    else:
        print(f"  numbers on this account: {len(nums)}")
        for n in nums:
            print(f"    - {n.get('phone_number')} ({n.get('friendly_name')})")


def _hydrate_twilio_from_db(settings, db_path: str) -> None:
    """Load Twilio credentials the way the app does at startup.

    They are NOT in .env — an admin saved them through Settings -> Integrations,
    so they live Fernet-encrypted in integration_configs. Mirrors
    app.integrations.settings_router.load_integration_configs for a sync script.
    """
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT encrypted_config FROM integration_configs WHERE integration_type = 'twilio'"
        ).fetchone()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"(could not read integration_configs: {exc})")
        return
    if not row:
        return

    from app.core.encryption import get_encryption_service, init_encryption_service

    try:
        get_encryption_service()
    except RuntimeError:
        init_encryption_service(settings.fernet_key)

    cfg = json.loads(get_encryption_service().decrypt(row[0]))
    for field, attr in (
        ("account_sid", "twilio_account_sid"),
        ("auth_token", "twilio_auth_token"),
        ("from_number", "twilio_from_number"),
    ):
        if cfg.get(field):
            setattr(settings, attr, cfg[field])
    print("(twilio credentials loaded from the encrypted integration config)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="Snapshot path (default: ./telephony_geo_snapshot_<ts>.json)")
    ap.add_argument("--db", default="data/accountant.db")
    args = ap.parse_args()

    settings = Settings()
    _hydrate_twilio_from_db(settings, args.db)
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print("Twilio is not configured (checked .env and integration_configs).")
        return 1

    from twilio.rest import Client

    parent = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    snapshots = [_snapshot(parent, f"parent:{settings.twilio_account_sid}")]

    # Every subaccount we track locally, using ITS OWN credentials.
    try:
        conn = sqlite3.connect(args.db)
        rows = conn.execute(
            "SELECT tenant_key, subaccount_sid, encrypted_auth_token FROM telephony_accounts"
        ).fetchall()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"(could not read telephony_accounts: {exc})")
        rows = []

    if rows:
        from app.core.encryption import get_encryption_service, init_encryption_service

        try:
            get_encryption_service()
        except RuntimeError:
            init_encryption_service(settings.fernet_key)
        enc = get_encryption_service()
        for tenant_key, sid, tok in rows:
            try:
                sub = Client(sid, enc.decrypt(tok))
                snapshots.append(_snapshot(sub, f"subaccount:{tenant_key}:{sid}"))
            except Exception as exc:  # noqa: BLE001
                snapshots.append({"label": f"subaccount:{tenant_key}:{sid}", "__error__": str(exc)[:200]})

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "parent_sid": settings.twilio_account_sid,
        "subaccounts_found": len(rows),
        "snapshots": snapshots,
    }

    out = args.out or f"telephony_geo_snapshot_{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== TWILIO GEO PERMISSIONS — CURRENT STATE (read-only) ===")
    print(f"parent: {settings.twilio_account_sid}")
    print(f"subaccounts tracked locally: {len(rows)}")
    for snap in snapshots:
        if "__error__" in snap and "label" in snap:
            print(f"\n--- {snap['label']} ---\n  ERROR {snap['__error__']}")
        else:
            _summarize(snap)
    print(f"\nSnapshot written: {out}")
    print("Keep this file — it is the rollback reference for the geo change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
