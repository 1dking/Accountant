"""Canonical versions + copy for legal / consent surfaces.

Single source of truth so a consent record, the privacy-policy page, and the
Plaid Link consent panel all reference the SAME version string. Bump the version
whenever the corresponding text changes — existing consent rows keep the version
they were captured under, which is exactly what the "provide records on request"
obligation needs.

NOTE: the privacy-policy / terms bodies are deliberate PLACEHOLDERS. They state
the data practices that the code actually implements, but they are not a
substitute for lawyer-reviewed copy. Replace the bodies (not necessarily the
versions) before launch; bump the version when you do.
"""

# Bump these whenever the referenced text changes. The privacy/terms bodies are
# the OCIDM v0.2 documents (frontend/src/pages/{PrivacyPolicy,Terms}Page).
PRIVACY_POLICY_VERSION = "0.2"
TERMS_VERSION = "0.2"
PLAID_CONSENT_VERSION = "2026-07-24"

#: Shown, verbatim and conspicuously, in the Plaid Link consent step. Must state
#: WHAT is collected, HOW it is used, and that it is not sold or shared. The
#: exact text is persisted on every consent row (see PlaidConsent.consent_text)
#: so we can prove what a user actually agreed to.
PLAID_CONSENT_TEXT = (
    "By connecting a bank account you authorize this application to use Plaid to "
    "securely access your bank account and transaction history (transactions "
    "product only). We use this information solely to import and categorize "
    "transactions for bookkeeping within your own account. We do not sell your "
    "financial data and do not share it except with Plaid and the service "
    "providers strictly necessary to operate this feature. You can disconnect a "
    "bank account at any time, which stops further access and deletes the stored "
    "connection. See our Privacy Policy for full details."
)

#: The Plaid product scope this consent authorizes.
PLAID_PRODUCT_SCOPE = "transactions"
