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

    # --- 1. Pumping protection (additive) --------------------------------
    from app.communication.telephony import apply_sms_pumping_protection

    pumping = apply_sms_pumping_protection(client, f"parent:{settings.twilio_account_sid}")
    print(f"\npumping protection: {pumping.get('pumping_protection')}")

    # --- 2. Enable US + CA voice (additive) ------------------------------
    perms = _dialing(client)
    for iso in ALLOW:
        try:
            perms.countries(iso).update(low_risk_numbers_enabled=True)
            print(f"voice: enabled {iso}")
        except Exception as exc:  # noqa: BLE001
            print(f"voice: FAILED to enable {iso}: {type(exc).__name__}: {str(exc)[:140]}")

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

    svcs_after = _messaging_services(client)
    print("pumping protection now: "
          f"{[s.get('sms_pumping_risk_check_enabled') for s in svcs_after]}")
    print("\nOK — additive changes only, nothing removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
