"""Sub-account onboarding presets — which modules a client tenant starts with.

The feature gate (dependencies._tenant_allows_feature) is SUBTRACTIVE: a
SubAccountFeature row with enabled=False denies; no row allows. So a preset
is just the set of modules to switch OFF at provisioning time.

Two channels, two presets:

  MARKETING_AGENCY — "books off by default". An agency resells website +
      forms + CRM + phone + meetings to its clients. The accounting modules
      stay dark until the client's accountant (or the operator) unlocks them,
      so the agency never carries ledger liability it didn't sign up for.

  ACCOUNTING_PRACTICE — "books first". An accounting firm provisions a client
      with everything on; nothing is denied.

  CUSTOM — nothing seeded; the operator toggles by hand.
"""
from __future__ import annotations

from app.operators.models import OnboardingTemplate

#: The accounting bundle — what "unlock books" turns on and "lock books" turns off.
BOOKS_FEATURES: tuple[str, ...] = (
    "cashbook",
    "expenses",
    "smart_import",
    "email_scanner",
    "reports",
    "tax",
    "recurring",
)

#: Modules denied at provisioning, per template. Only denies are listed.
TEMPLATE_DENIES: dict[OnboardingTemplate, tuple[str, ...]] = {
    OnboardingTemplate.MARKETING_AGENCY: BOOKS_FEATURES + ("obrain_coach", "platform_admin"),
    OnboardingTemplate.ACCOUNTING_PRACTICE: ("platform_admin",),
    OnboardingTemplate.CUSTOM: (),
}

TEMPLATE_LABELS: dict[OnboardingTemplate, tuple[str, str]] = {
    OnboardingTemplate.MARKETING_AGENCY: (
        "Agency client",
        "Website, forms, CRM, phone and meetings. Books stay off until their accountant unlocks them.",
    ),
    OnboardingTemplate.ACCOUNTING_PRACTICE: (
        "Accounting client",
        "Everything on, books first. For firms provisioning a client they keep the books for.",
    ),
    OnboardingTemplate.CUSTOM: (
        "Custom",
        "Start with everything on and switch modules off by hand.",
    ),
}
