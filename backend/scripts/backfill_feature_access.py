#!/usr/bin/env python
"""Expand PARTIAL feature_access maps into complete, explicit grids.

Why: resolve_feature_access() used to merge a selection over the role defaults,
so a map that omitted a key silently inherited that key from the role preset
(true for most roles). It is now fail-closed — an explicit selection is
authoritative. Any user whose stored map is INCOMPLETE would therefore lose the
features they were implicitly getting.

This freezes each such user's CURRENT effective access into a complete map, so
flipping the semantics changes nothing for existing accounts. Run it BEFORE
deploying the resolver change.

It deliberately PRESERVES access rather than tightening it — features that were
only granted implicitly become explicit `true`, and are then visible (and
un-checkable) in the admin UI. Review those users afterwards if you want them
narrowed.

Dry-run by default:
  .venv/bin/python scripts/backfill_feature_access.py
  .venv/bin/python scripts/backfill_feature_access.py --apply
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.features import ALL_FEATURES, ROLE_DEFAULTS  # noqa: E402

_ALL_FALSE = {f: False for f in ALL_FEATURES}


def legacy_effective(role: str, stored: dict) -> dict:
    """Reproduce the OLD merge semantics: role defaults, overridden by the map."""
    resolved = ROLE_DEFAULTS.get(role, _ALL_FALSE).copy()
    for k, v in stored.items():
        if k in resolved and isinstance(v, bool):
            resolved[k] = v
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    ap.add_argument("--db", default="data/accountant.db", help="Path to the SQLite DB")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT id, email, role, feature_access_json FROM users"
    ).fetchall()

    changed = 0
    for uid, email, role, fa in rows:
        if not fa:
            continue  # no explicit map -> role preset, unaffected
        try:
            stored = json.loads(fa)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(stored, dict):
            continue

        missing = [f for f in ALL_FEATURES if f not in stored]
        if not missing:
            continue  # already complete

        role_key = (role or "").lower()
        complete = legacy_effective(role_key, stored)
        implicit_grants = [f for f in missing if complete.get(f)]

        print(f"{email} (role={role}): {len(missing)} key(s) missing -> completing map")
        if implicit_grants:
            print(f"    previously-implicit grants now explicit: {implicit_grants}")

        if args.apply:
            conn.execute(
                "UPDATE users SET feature_access_json = ? WHERE id = ?",
                (json.dumps(complete), uid),
            )
        changed += 1

    if args.apply:
        conn.commit()
    conn.close()

    mode = "APPLIED" if args.apply else "DRY-RUN (no changes written)"
    print(f"\n=== {mode} === users needing backfill: {changed} / {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
