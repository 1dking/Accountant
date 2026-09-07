/** Thin fetch wrapper against /api/pages/public/{slug}. */
export interface PagesGlobal {
  slug: string
  api: string
  locale: string
  version: string
}

declare global {
  interface Window { __PAGES__?: PagesGlobal }
}

export function pagesConfig(): PagesGlobal {
  const g = window.__PAGES__
  if (g) return g
  const slug = location.pathname.split('/').filter(Boolean).pop() || ''
  return { slug, api: `/api/pages/public/${slug}`, locale: document.documentElement.lang || 'en', version: 'dev' }
}

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${pagesConfig().api}${path}`, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json() as Promise<T>
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${pagesConfig().api}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json() as Promise<T>
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const j = await res.json()
    const d = j?.detail ?? j?.error?.message ?? j?.message
    if (typeof d === 'string') return d
  } catch { /* not json */ }
  return res.status === 429 ? t('tooMany') : t('failed')
}

const STRINGS: Record<string, Record<string, string>> = {
  en: {
    failed: 'Something went wrong. Please try again.',
    tooMany: 'Too many attempts. Please wait a moment.',
    sending: 'Sending…',
    sent: 'Thanks — we’ll be in touch shortly.',
    booking: 'Booking…',
    booked: 'You’re booked!',
    noSlots: 'No openings on this day.',
    pickTime: 'Pick a time',
    yourDetails: 'Your details',
    name: 'Name', email: 'Email', phone: 'Phone (optional)', notes: 'Notes (optional)',
    confirm: 'Confirm booking', back: 'Back',
    days: 'days', hours: 'hours', minutes: 'min', seconds: 'sec',
    expired: 'This offer has ended.',
    openNow: 'Open now', closedNow: 'Closed now', opensAt: 'Opens {t}', closesAt: 'Closes {t}',
    estimate: 'Estimated total', noResults: 'No matching questions.',
  },
  'fr-CA': {
    failed: 'Une erreur est survenue. Veuillez réessayer.',
    tooMany: 'Trop de tentatives. Veuillez patienter un instant.',
    sending: 'Envoi…',
    sent: 'Merci — nous vous répondrons sous peu.',
    booking: 'Réservation…',
    booked: 'Votre rendez-vous est confirmé!',
    noSlots: 'Aucune disponibilité ce jour-là.',
    pickTime: 'Choisissez une heure',
    yourDetails: 'Vos coordonnées',
    name: 'Nom', email: 'Courriel', phone: 'Téléphone (facultatif)', notes: 'Notes (facultatif)',
    confirm: 'Confirmer le rendez-vous', back: 'Retour',
    days: 'jours', hours: 'heures', minutes: 'min', seconds: 's',
    expired: 'Cette offre est terminée.',
    openNow: 'Ouvert', closedNow: 'Fermé', opensAt: 'Ouvre à {t}', closesAt: 'Ferme à {t}',
    estimate: 'Total estimé', noResults: 'Aucune question correspondante.',
  },
}

export function t(key: string, vars?: Record<string, string | number>): string {
  const loc = pagesConfig().locale
  const table = STRINGS[loc] ?? STRINGS[loc.split('-')[0]] ?? STRINGS.en
  let s = table[key] ?? STRINGS.en[key] ?? key
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v))
  return s
}

export function money(amount: number, currency = 'CAD'): string {
  try {
    return new Intl.NumberFormat(pagesConfig().locale, { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currency}`
  }
}

/** Parse the block's data-block-config JSON (runtime fields ⊕ id). */
export function blockConfig<T extends object>(el: Element): T {
  try {
    return JSON.parse(el.getAttribute('data-block-config') || '{}') as T
  } catch {
    return {} as T
  }
}
