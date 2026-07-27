#!/usr/bin/env python
"""Disable HIGH-RISK voice ranges while leaving normal calling untouched.

Why this and not "deny all but US/CA": the captured snapshot showed all 37
callable countries with ``high_risk_tollfraud_numbers_enabled`` on (and 29 with
``high_risk_special_numbers_enabled``). Those are the premium-rate ranges
toll-fraud actually dials — the expensive part. Blanket country denial would also
stop ordinary business calls to the UK, Germany, Mexico and so on, which is a
product decision; turning off high-risk ranges is not, because no normal call
lands on them.

What this does, per country that currently has either high-risk flag on:
    high_risk_tollfraud_numbers_enabled -> False
    high_risk_special_numbers_enabled   -> False
    low_risk_numbers_enabled            -> LEFT AT ITS CURRENT VALUE

That last line is the important one. The bulk API takes the full flag set per
country, so the current low-risk value is read and echoed back; if it were
omitted the API could default it off and silently kill normal calling. The
verification step fails the run if the low-risk set changes at all.

Usage (from backend/):
  .venv/bin/python scripts/telephony_disable_high_risk_voice.py            # dry run
  .venv/bin/python scripts/telephony_disable_high_risk_voice.py --apply
Rollback: backups/telephony/geo_snapshot_pre_hardening.json holds the original
per-country flags; re-apply them with the same bulk endpoint.
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

from app.config import Settings  # noqa: E402
from telephony_geo_capture import _hydrate_twilio_from_db, _voice_permissions  # noqa: E402

CHUNK = 25  # keep each bulk request modest


def _dialing(client):
    v1 = getattr(getattr(client, "voice", None), "v1", None)
    if v1 is not None and hasattr(v1, "dialing_permissions"):
        return v1.dialing_permissions
    return client.voice.dialing_permissions


def _low_risk_set(perms: dict) -> set:
    return {iso for iso, v in perms.items() if v.get("low_risk_numbers_enabled")}


def _high_risk_targets(perms: dict) -> list:
    return sorted(
        iso
        for iso, v in perms.items()
        if v.get("high_risk_tollfraud_numbers_enabled")
        or v.get("high_risk_special_numbers_enabled")
    )


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

    before = _voice_permissions(client)
    if "__error__" in before:
        print(f"could not read permissions: {before['__error__']}")
        return 1

    low_before = _low_risk_set(before)
    targets = _high_risk_targets(before)

    print(f"countries listed: {len(before)}")
    print(f"normal (low-risk) calling enabled on: {len(low_before)}")
    print(f"countries with a HIGH-RISK range enabled: {len(targets)}")
    print(f"  {', '.join(targets) if targets else 'none'}")

    if not targets:
        print("\nNothing to do — no high-risk ranges are enabled.")
        return 0

    if not args.apply:
        print(f"\nDRY RUN — would turn OFF both high-risk flags on {len(targets)} countries,")
        print("and leave low_risk_numbers_enabled exactly as it is (normal calling unaffected).")
        print("Nothing else is touched. Re-run with --apply to write.")
        return 0

    perms = _dialing(client)
    errors: list[str] = []
    for i in range(0, len(targets), CHUNK):
        batch = targets[i : i + CHUNK]
        payload = [
            {
                "iso_code": iso,
                # Echo the CURRENT low-risk value so normal calling is preserved.
                "low_risk_numbers_enabled": bool(
                    before[iso].get("low_risk_numbers_enabled")
                ),
                "high_risk_special_numbers_enabled": False,
                "high_risk_tollfraud_numbers_enabled": False,
            }
            for iso in batch
        ]
        try:
            perms.bulk_country_updates.create(update_request=json.dumps(payload))
            print(f"submitted batch {i // CHUNK + 1}: {', '.join(batch)}")
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            print(f"batch {i // CHUNK + 1} FAILED: {msg}")
            errors.append(msg)

    # --- Verify -----------------------------------------------------------
    after = _voice_permissions(client)
    low_after = _low_risk_set(after)
    still_high = _high_risk_targets(after)

    lost = sorted(low_before - low_after)
    print(f"\nnormal calling before: {len(low_before)}  after: {len(low_after)}")
    print(f"countries that LOST normal calling: {lost or 'none'}")
    print(f"countries still having a high-risk range: {still_high or 'none'}")

    if lost:
        print(
            "\n*** REGRESSION: normal calling was removed from the countries above. "
            "Restore from backups/telephony/geo_snapshot_pre_hardening.json. ***"
        )
        return 2
    if errors or still_high:
        print("\nINCOMPLETE — high-risk ranges remain enabled (or a batch failed).")
        return 3

    print("\nOK — high-risk ranges disabled everywhere; normal calling unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
