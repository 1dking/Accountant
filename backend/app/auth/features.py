"""Canonical feature list and role-based defaults for per-user feature access."""

import json
from typing import Optional

FEATURE_CATEGORIES: dict[str, list[str]] = {
    "CRM": ["contacts", "pipeline", "tasks", "cards"],
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
        "cards": True,
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
    """Resolve effective features.

    No explicit selection  -> the role's default preset.
    An explicit selection  -> AUTHORITATIVE and FAIL-CLOSED: a feature the
                              selection does not mention is NOT granted.

    The fail-closed half matters. This previously merged the selection *over* the
    role defaults, so any key the selection omitted kept its default — and
    team_member/manager default to every feature true. Consequences seen in
    practice:
      * selecting a single module for a team_member granted 29 features, and the
        account could open modules the admin never picked;
      * a stale cached frontend bundle submitting a grid from before a feature key
        existed silently granted that new feature to everyone it created.
    An admin who wants a role's full preset simply leaves the selection unset.
    """
    defaults = ROLE_DEFAULTS.get(role, _ALL_FALSE).copy()
    if not feature_access_json:
        return defaults
    try:
        overrides = json.loads(feature_access_json)
    except (json.JSONDecodeError, TypeError):
        return defaults
    if not isinstance(overrides, dict) or not overrides:
        # An EMPTY map is not a selection — it means "no per-user overrides", so
        # fall back to the role preset. (Unchecking every box in the admin UI
        # sends a full grid of false values, not {}, and that correctly grants
        # nothing via the fail-closed path below.)
        return defaults

    resolved = _ALL_FALSE.copy()
    for key, val in overrides.items():
        if key in resolved and isinstance(val, bool):
            resolved[key] = val
    return resolved
