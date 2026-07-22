/**
 * Canonical feature list and role-based defaults.
 * Must stay in sync with backend/app/auth/features.py.
 */

export const FEATURE_CATEGORIES: Record<string, string[]> = {
  CRM: ['contacts', 'pipeline', 'tasks'],
  Sales: ['invoices', 'estimates', 'proposals'],
  Accounting: [
    'cashbook',
    'expenses',
    'smart_import',
    'email_scanner',
    'reports',
    'tax',
    'recurring',
  ],
  Communication: ['inbox', 'phone', 'sms'],
  Automation: ['workflows', 'forms'],
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
  manager: { ...allTrue, platform_admin: false },
  team_member: { ...allTrue, platform_admin: false },
  accountant: {
    ...allFalse,
    cashbook: true,
    expenses: true,
    invoices: true,
    estimates: true,
    contacts: true,
    smart_import: true,
    email_scanner: true,
    reports: true,
    tax: true,
    recurring: true,
    drive: true,
  },
  client: { ...allFalse },
  // A viewer is a read-only collaborator: it owns nothing and sees only what is
  // shared with it. It needs the contacts module on, or it would be handed a
  // record it cannot open.
  viewer: { ...allFalse, contacts: true },
}

/**
 * Route prefix → the module it belongs to.
 *
 * Hiding a sidebar link does nothing to stop someone typing /cashbook into the
 * address bar, and every route in App.tsx was reachable that way. ProtectedRoute
 * resolves the LONGEST matching prefix, so new routes inherit a guard by default
 * rather than being silently unguarded.
 *
 * The backend is the real gate (require_feature). This is defence in depth, and
 * the difference between a bounced route and a page that renders then explodes
 * into 403s.
 */
export const ROUTE_FEATURES: Array<[string, string]> = [
  ['/contacts', 'contacts'],
  ['/tasks', 'tasks'],
  ['/invoices', 'invoices'],
  ['/estimates', 'estimates'],
  ['/proposals', 'proposals'],
  ['/cashbook', 'cashbook'],
  ['/reconcile', 'cashbook'],
  ['/expenses', 'expenses'],
  ['/income', 'expenses'],
  ['/budgets', 'expenses'],
  ['/reports', 'reports'],
  ['/recurring', 'recurring'],
  ['/smart-import', 'smart_import'],
  ['/email-scan', 'email_scanner'],
  ['/inbox', 'inbox'],
  ['/conversations', 'phone'],
  ['/communication', 'phone'],
  ['/drive', 'drive'],
  ['/documents', 'drive'],
  ['/meetings', 'meeting_rooms'],
  ['/calendar', 'calendar'],
  ['/bookings', 'calendar'],
  ['/availability', 'calendar'],
  ['/scheduling', 'calendar'],
  ['/pages', 'pages'],
  ['/forms', 'forms'],
  ['/workflows', 'workflows'],
  ['/docs', 'docs'],
  ['/obrain', 'obrain_chat'],
  ['/intelligence', 'obrain_coach'],
  ['/platform-admin', 'platform_admin'],
  ['/admin', 'platform_admin'],
]

/** The feature a path belongs to, or null if the path is always allowed. */
export function featureForPath(pathname: string): string | null {
  let best: [string, string] | null = null
  for (const entry of ROUTE_FEATURES) {
    if (pathname === entry[0] || pathname.startsWith(entry[0] + '/')) {
      if (!best || entry[0].length > best[0].length) best = entry
    }
  }
  return best ? best[1] : null
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

/**
 * Does this user have the module?
 *
 * FAILS CLOSED. This used to `return true` when featureAccess was null, on a
 * "backward compat" rationale — which meant any user whose payload lacked the
 * field saw the entire nav. Combined with the backend never checking the flag at
 * all, a module being "off" meant nothing whatsoever.
 *
 * Callers must not evaluate this while the user is still loading, or it will
 * briefly deny everything. Gate on the auth store's loading state first —
 * ProtectedRoute does.
 */
export function hasFeature(
  featureAccess: Record<string, boolean> | null | undefined,
  key: string,
): boolean {
  if (!featureAccess) return false
  return featureAccess[key] === true
}
