"""Schema for editable email templates.

Each entry declares:
  - ``label``: human-readable name shown in the Settings UI
  - ``description``: when this template fires
  - ``default_subject``: subject when no override is set
  - ``variables``: list of ``{placeholder}`` names the admin may use
                   in the body / subject override. Validated server-
                   side so admins can't reference variables we never
                   pass in (those would render as the literal text
                   "{whatever}" and look broken).
  - ``allows_body_override``: False for templates whose system version
                   relies on dynamic structures (e.g. invoice line-item
                   tables) that a flat-string override can't reproduce.
                   Subject override still works.
  - ``warnings``: optional list of strings shown in the editor UI,
                   e.g. "this template includes a line items table —
                   overriding the body removes it".

Single source of truth for both the validator and the UI.
"""
from __future__ import annotations

from typing import TypedDict


class TemplateSchema(TypedDict, total=False):
    label: str
    description: str
    default_subject: str
    variables: list[str]
    allows_body_override: bool
    warnings: list[str]


# template_key -> schema
TEMPLATES: dict[str, TemplateSchema] = {
    "password_reset": {
        "label": "Password reset",
        "description": "Sent when a user requests a password reset link.",
        "default_subject": "Reset your password",
        "variables": ["user_name", "reset_url", "expires_in", "company_name"],
        "allows_body_override": True,
    },
    "invite": {
        "label": "Team invitation",
        "description": "Sent when an admin creates a user with send_invite=true.",
        "default_subject": "You're invited",
        "variables": ["full_name", "invite_link", "company_name"],
        "allows_body_override": True,
    },
    "notification": {
        "label": "In-app notification (email channel)",
        "description": (
            "Sent for any notification where the user has the email "
            "channel enabled in Notification Preferences."
        ),
        "default_subject": "[{company_name}] {title}",
        "variables": [
            "title",
            "message",
            "link_url",
            "link_label",
            "type_label",
            "company_name",
            "preferences_url",
        ],
        "allows_body_override": True,
    },
    "payment_confirmation": {
        "label": "Payment confirmation",
        "description": "Sent to the customer when an invoice is fully paid.",
        "default_subject": "Payment received — Invoice {invoice_number}",
        "variables": [
            "invoice_number",
            "amount",
            "currency",
            "payment_date",
            "payment_method",
            "company_name",
        ],
        "allows_body_override": True,
    },
    "invoice": {
        "label": "Invoice email",
        "description": "Sent when an invoice is dispatched to a contact.",
        "default_subject": "Invoice {invoice_number}",
        "variables": [
            "invoice_number",
            "total",
            "currency",
            "due_date",
            "contact_name",
            "custom_message",
            "company_name",
        ],
        "allows_body_override": False,
        "warnings": [
            "This template includes an itemized line-items table. "
            "Subject is editable, but the body uses dynamic structures "
            "that can't be replaced with a static placeholder body."
        ],
    },
    "payment_reminder": {
        "label": "Payment reminder",
        "description": "Sent to nudge a contact about an overdue invoice.",
        "default_subject": "Payment Reminder: Invoice {invoice_number}",
        "variables": [
            "invoice_number",
            "total",
            "currency",
            "days_overdue",
            "contact_name",
            "company_name",
        ],
        "allows_body_override": False,
        "warnings": [
            "This template includes invoice details rendered as a "
            "structured block. Subject is editable; body override is "
            "disabled to preserve the layout."
        ],
    },
    "estimate": {
        "label": "Estimate email",
        "description": "Sent when an estimate is dispatched to a contact.",
        "default_subject": "Estimate {estimate_number}",
        "variables": [
            "estimate_number",
            "total",
            "currency",
            "contact_name",
            "view_url",
            "custom_message",
            "company_name",
        ],
        "allows_body_override": False,
        "warnings": [
            "This template includes a line-items table. Subject "
            "is editable; body override is disabled."
        ],
    },
}


def get_schema(template_key: str) -> TemplateSchema | None:
    return TEMPLATES.get(template_key)


def template_keys() -> list[str]:
    """All editable template keys, in the order the UI should show them."""
    return list(TEMPLATES.keys())
