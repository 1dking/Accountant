#!/usr/bin/env python
"""Apply ONLY the two additive telephony safety changes. Nothing is disabled.

Scope, deliberately narrow:

  1. Enable SMS Pumping Protection on every messaging service. This only turns a
     risk check ON — it cannot block a destination that currently works.
  2. Enable VOICE for CA (and confirm US). The captured snapshot showed CA was
     DISABLED while two of our own numbers are Canadian, so this is a fix, not a
     restriction.

What this script explicitly does NOT do: disable any country. The pre-hardening
snapshot showed 37 voice countries enabled; blanket-denying the other 35 is a real
behaviour change that needs a human decision, so it is out of scope here.

Verification: prints the enabled-country set before and after and asserts the
after-set is a strict SUPERSET of the before-set — proving nothing was removed.

Usage (from backend/):
  .venv/bin/python scripts/telephony_apply_safe_hardening.py            # dry run
  .venv/bin/python scripts/telephony_apply_safe_hardening.py --apply
"""
import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # backend/
sys.path.insert(0, str(_HERE))         # scripts/

from app.config import Settings  # noqa: E402
from telephony_geo_capture import (  # noqa: E402
    _hydrate_twilio_from_db,
    _messaging_services,
    _voice_permissions,
)

ALLOW = ("US", "CA")


def _enabled_set(client) -> set:
    perms = _voice_permissions(client)
    if "__error__" in perms:
        return set()
    return {iso for iso, v in perms.items() if v.get("low_risk_numbers_enabled")}


def _dialing(client):
    """Prefer the non-deprecated v1 path, fall back for older SDKs."""
    v1 = getattr(getattr(client, "voice", None), "v1", None)
    if v1 is not None and hasattr(v1, "dialing_permissions"):
        return v1.dialing_permissions
    return client.voice.dialing_permissions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    ap.add_argument("--db", default="data/accountant.db")
    args = ap.parse_args()

    settings = Settings()
    _hydrate_twilio_from_db(settings, args.db)
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print("Twilio is not configured.")
        return 1

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    before = _enabled_set(client)
    services = _messaging_services(client)
    print(f"BEFORE: {len(before)} voice countries enabled; CA={'yes' if 'CA' in before else 'NO'}")
    print(f"BEFORE: {len(services)} messaging service(s), pumping protection states: "
          f"{[s.get('sms_pumping_risk_check_enabled') for s in services]}")

    if not args.apply:
        print("\nDRY RUN — would:")
        print(f"  * enable voice for {', '.join(a for a in ALLOW if a not in before) or '(nothing, already enabled)'}")
        print(f"  * enable SMS pumping protection on {len(services)} messaging service(s)")
        print("  * disable NOTHING")
        return 0

    failures: list[str] = []

    # --- 1. SMS Pumping Protection ---------------------------------------
    # NOT settable through twilio-python 9.10.2: ServiceContext.update() exposes
    # no sms_pumping_risk_check_enabled parameter (verified by introspecting the
    # SDK signature). It is a Console-side Messaging setting, so this reports it
    # as a required manual step instead of pretending to configure it.
    print("\npumping protection: MANUAL — not settable via this SDK "
          "(Twilio Console > Messaging > Settings). All services currently OFF.")
    failures.append("sms_pumping_protection — must be enabled in the Twilio Console")

    # --- 2. Enable US + CA voice (additive) ------------------------------
    # Individual country resources are READ-ONLY here; enabling/disabling goes
    # through bulk_country_updates.
    import json as _json

    to_enable = [iso for iso in ALLOW if iso not in before]
    if not to_enable:
        print("voice: US and CA already enabled — nothing to do")
    else:
        try:
            _dialing(client).bulk_country_updates.create(
                update_request=_json.dumps(
                    {"add_countries": to_enable, "add_low_risk_numbers": True}
                )
            )
            print(f"voice: submitted bulk enable for {', '.join(to_enable)}")
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            print(f"voice: FAILED bulk enable for {', '.join(to_enable)}: {msg}")
            failures.append(f"voice_enable({','.join(to_enable)}): {msg}")

    # --- Verify nothing was removed --------------------------------------
    after = _enabled_set(client)
    removed = sorted(before - after)
    added = sorted(after - before)
    print(f"\nAFTER: {len(after)} voice countries enabled; CA={'yes' if 'CA' in after else 'NO'}")
    print(f"added: {added or 'none'}")
    print(f"removed: {removed or 'none'}")

    if removed:
        print("\n*** WARNING: countries were REMOVED. That was not intended by this "
              "script — restore from the snapshot and investigate. ***")
        return 2

    if "CA" not in after:
        failures.append("voice_enable(CA) — still not enabled after apply")

    if failures:
        # Exit NON-ZERO. The first version of this script printed
        # "OK — nothing removed" and returned 0 even though BOTH intended changes
        # had silently failed, which reads as success. Failing to apply a safety
        # control is a failure, not a no-op.
        print("\nINCOMPLETE — the following did NOT take effect:")
        for f in failures:
            print(f"  - {f}")
        return 3

    print("\nOK — additive changes applied, nothing removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
