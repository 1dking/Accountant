"""Canonical feature list and role-based defaults for per-user feature access."""

import json
from typing import Optional

FEATURE_CATEGORIES: dict[str, list[str]] = {
    "CRM": ["contacts", "pipeline", "tasks"],
    "Sales": ["invoices", "estimates", "proposals"],
    "Accounting": [
        "cashbook",
        "expenses",
        "smart_import",
        "email_scanner",
        "reports",
        "tax",
        "recurring",
    ],
    "Communication": ["inbox", "phone", "sms"],
    "Automation": ["workflows", "forms"],
    "Content": ["pages", "docs", "sheets", "slides"],
    "Storage": ["drive"],
    "Meetings": ["calendar", "meeting_rooms"],
    "AI": ["obrain_chat", "obrain_coach"],
    "Admin": ["platform_admin", "portal_admin"],
}
# `estimates`, `expenses`, `tasks`, `workflows` and `forms` were added when the
# module gate was actually enforced: those routers previously had NO feature key,
# so there was no way to switch them off for an employee. Adding a key here
# automatically widens the admin checkbox grid — the UI reads this dict.

ALL_FEATURES: list[str] = [f for feats in FEATURE_CATEGORIES.values() for f in feats]

_ALL_TRUE = {f: True for f in ALL_FEATURES}
_ALL_FALSE = {f: False for f in ALL_FEATURES}

ROLE_DEFAULTS: dict[str, dict[str, bool]] = {
    "admin": {**_ALL_TRUE},
    # Same modules as a team member. A manager's extra power is VISIBILITY (it
    # sees its direct reports' records), not extra sections.
    "manager": {**_ALL_TRUE, "platform_admin": False},
    "team_member": {**_ALL_TRUE, "platform_admin": False},
    # An accountant runs the money side end to end: they handle the invoices that
    # come in from email, so they get invoicing (invoices + estimates) and the
    # contacts to invoice against, on top of the accounting modules. contacts is
    # only the MODULE — records stay owner-private, so they still see only their
    # own contacts, not the whole agency's.
    "accountant": {
        **_ALL_FALSE,
        "cashbook": True,
        "expenses": True,
        "invoices": True,
        "estimates": True,
        "contacts": True,
        "smart_import": True,
        "email_scanner": True,
        "reports": True,
        "tax": True,
        "recurring": True,
        "drive": True,
    },
    "client": {**_ALL_FALSE},
    # A viewer is a read-only collaborator: it owns nothing and sees only what is
    # explicitly SHARED with it. It still needs the contacts module switched on,
    # or the module gate would block the very share it was granted — it would be
    # handed a record it cannot open.
    "viewer": {**_ALL_FALSE, "contacts": True},
}

#: These are DEFAULTS, not policy. An admin overrides any of them per user via
#: feature_access_json (PlatformAdminPage → FeatureAccessEditor).


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
