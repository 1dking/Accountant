// Legal document versions shown in the app.
//
// Keep these in sync with the backend source of truth in
// backend/app/core/legal.py — the backend is authoritative and stamps the
// version onto each Plaid consent record; these mirror it for display. The
// pages also fetch /api/legal/versions at runtime and prefer that value, so a
// backend bump shows up even if this constant lags.
export const PRIVACY_POLICY_VERSION = '1.1'
export const TERMS_VERSION = '1.0'
export const PLAID_CONSENT_VERSION = '2026-07-24'
