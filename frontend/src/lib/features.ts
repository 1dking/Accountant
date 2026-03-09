/**
 * Canonical feature list and role-based defaults.
 * Must stay in sync with backend/app/auth/features.py.
 */

export const FEATURE_CATEGORIES: Record<string, string[]> = {
  CRM: ['contacts', 'pipeline'],
  Sales: ['invoices', 'proposals'],
  Accounting: ['cashbook', 'smart_import', 'email_scanner', 'reports', 'tax', 'recurring'],
  Communication: ['inbox', 'phone', 'sms'],
  Content: ['pages', 'docs', 'sheets', 'slides'],
  Storage: ['drive'],
  Meetings: ['calendar', 'meeting_rooms'],
  AI: ['obrain_chat', 'obrain_coach'],
  Admin: ['platform_admin', 'portal_admin'],
}

export const ALL_FEATURES = Object.values(FEATURE_CATEGORIES).flat()

const allTrue = Object.fromEntries(ALL_FEATURES.map(f => [f, true]))
const allFalse = Object.fromEntries(ALL_FEATURES.map(f => [f, false]))

export const ROLE_DEFAULTS: Record<string, Record<string, boolean>> = {
  admin: { ...allTrue },
  team_member: { ...allTrue, platform_admin: false },
  accountant: {
    ...allFalse,
    cashbook: true,
    smart_import: true,
    email_scanner: true,
    reports: true,
    tax: true,
    recurring: true,
    drive: true,
  },
  client: { ...allFalse },
  viewer: { ...allFalse },
}

export const FEATURE_LABELS: Record<string, string> = {
  contacts: 'Contacts',
  pipeline: 'Pipeline',
  invoices: 'Invoices',
  proposals: 'Proposals',
  cashbook: 'Cashbook',
  smart_import: 'Smart Import',
  email_scanner: 'Email Scanner',
  reports: 'Reports',
  tax: 'Tax',
  recurring: 'Recurring',
  inbox: 'Inbox',
  phone: 'Phone',
  sms: 'SMS',
  pages: 'Pages',
  docs: 'Docs',
  sheets: 'Sheets',
  slides: 'Slides',
  drive: 'Drive',
  calendar: 'Calendar',
  meeting_rooms: 'Meeting Rooms',
  obrain_chat: 'O-Brain Chat',
  obrain_coach: 'O-Brain Coach',
  platform_admin: 'Platform Admin',
  portal_admin: 'Portal Admin',
}

export function getEffectiveFeatures(
  role: string,
  featureAccess: Record<string, boolean> | null | undefined,
): Record<string, boolean> {
  const defaults = { ...(ROLE_DEFAULTS[role] ?? allFalse) }
  if (featureAccess) {
    for (const [key, val] of Object.entries(featureAccess)) {
      if (key in defaults && typeof val === 'boolean') {
        defaults[key] = val
      }
    }
  }
  return defaults
}

export function hasFeature(
  featureAccess: Record<string, boolean> | null | undefined,
  key: string,
): boolean {
  if (!featureAccess) return true // null = no restrictions (backward compat)
  return featureAccess[key] !== false
}
