"""Canonical feature list and role-based defaults for per-user feature access."""

import json
from typing import Optional

FEATURE_CATEGORIES: dict[str, list[str]] = {
    "CRM": ["contacts", "pipeline"],
    "Sales": ["invoices", "proposals"],
    "Accounting": [
        "cashbook",
        "smart_import",
        "email_scanner",
        "reports",
        "tax",
        "recurring",
    ],
    "Communication": ["inbox", "phone", "sms"],
    "Content": ["pages", "docs", "sheets", "slides"],
    "Storage": ["drive"],
    "Meetings": ["calendar", "meeting_rooms"],
    "AI": ["obrain_chat", "obrain_coach"],
    "Admin": ["platform_admin", "portal_admin"],
}

ALL_FEATURES: list[str] = [f for feats in FEATURE_CATEGORIES.values() for f in feats]

_ALL_TRUE = {f: True for f in ALL_FEATURES}
_ALL_FALSE = {f: False for f in ALL_FEATURES}

ROLE_DEFAULTS: dict[str, dict[str, bool]] = {
    "admin": {**_ALL_TRUE},
    "team_member": {**_ALL_TRUE, "platform_admin": False},
    "accountant": {
        **_ALL_FALSE,
        "cashbook": True,
        "smart_import": True,
        "email_scanner": True,
        "reports": True,
        "tax": True,
        "recurring": True,
        "drive": True,
    },
    "client": {**_ALL_FALSE},
    "viewer": {**_ALL_FALSE},
}


def resolve_feature_access(
    role: str,
    feature_access_json: Optional[str] = None,
) -> dict[str, bool]:
    """Resolve effective features: explicit JSON overrides role defaults."""
    defaults = ROLE_DEFAULTS.get(role, _ALL_FALSE).copy()
    if feature_access_json:
        try:
            overrides = json.loads(feature_access_json)
            if isinstance(overrides, dict):
                for key, val in overrides.items():
                    if key in defaults and isinstance(val, bool):
                        defaults[key] = val
        except (json.JSONDecodeError, TypeError):
            pass
    return defaults
