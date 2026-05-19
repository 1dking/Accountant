/**
 * Contacts tab — searchable list. Tap a contact's phone icon to
 * initiate a call via the Twilio device.
 *
 * Search filters client-side across name + company + phone. Server-
 * side search exists too but for the dialer use case (200 contacts
 * is normal) client-side is snappier and avoids extra round-trips
 * while typing.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Phone, Search, Users } from 'lucide-react'
import { listContacts } from '@/api/contacts'
import type { Contact } from '@/types/models'

function initialsFor(name: string | null, company: string): string {
  const source = name || company || '?'
  return source
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function formatPhone(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 11 && digits.startsWith('1')) {
    return `(${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  }
  return raw
}

interface Props {
  onDial: (number: string) => void
}

export default function ContactsTab({ onDial }: Props) {
  const [query, setQuery] = useState('')

  const contactsQuery = useQuery({
    queryKey: ['dialer-contacts-list'],
    // page_size capped to 100 — the backend pagination validator
    // rejects anything over 100 with a 422 (which is why this tab
    // silently rendered empty in the 2026-05-18 audit). 100 covers
    // the working set for any non-enterprise install; search narrows
    // beyond that.
    queryFn: () => listContacts({ page_size: 100 }),
  })

  const contacts: Contact[] = (contactsQuery.data?.data as Contact[]) || []

  // Filter — name OR company OR phone digits substring match. Only
  // contacts with a phone are dialable, so we hide the rest entirely
  // to avoid dead rows.
  const filtered = useMemo(() => {
    const dialable = contacts.filter((c) => !!c.phone)
    const q = query.trim().toLowerCase()
    if (!q) return dialable
    const qDigits = q.replace(/\D/g, '')
    return dialable.filter((c) => {
      if (c.contact_name?.toLowerCase().includes(q)) return true
      if (c.company_name?.toLowerCase().includes(q)) return true
      if (qDigits && c.phone?.replace(/\D/g, '').includes(qDigits)) return true
      return false
    })
  }, [contacts, query])

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="px-5 pt-4 pb-3 shrink-0">
        <div className="lg-card flex items-center gap-2 px-3 py-2">
          <Search className="h-4 w-4 text-[color:var(--lg-text-muted)]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search contacts…"
            aria-label="Search contacts"
            className="flex-1 bg-transparent text-sm text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-muted)] outline-none"
          />
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {contactsQuery.isLoading ? (
          <p className="px-3 py-6 text-sm text-[color:var(--lg-text-muted)]">Loading contacts…</p>
        ) : contactsQuery.isError ? (
          // Surface fetch errors instead of falling through to the
          // "no contacts" empty state. The audit caught this — when
          // page_size=200 returned 422, the empty state masked a real
          // API failure.
          <div className="px-3 py-12 text-center">
            <Users className="h-8 w-8 mx-auto text-red-400 mb-3" />
            <p className="text-sm text-red-500 dark:text-red-400">Couldn't load contacts</p>
            <p className="text-xs text-[color:var(--lg-text-muted)] mt-1">
              {(contactsQuery.error as any)?.message || 'Try refreshing the page'}
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-3 py-12 text-center">
            <Users className="h-8 w-8 mx-auto text-[color:var(--lg-text-muted)] mb-3" />
            <p className="text-sm text-[color:var(--lg-text-secondary)]">
              {query ? 'No matches' : 'No contacts with phone numbers'}
            </p>
          </div>
        ) : (
          <ul className="space-y-1.5">
            {filtered.map((c) => {
              const displayName = c.contact_name || c.company_name
              const initials = initialsFor(c.contact_name, c.company_name)
              return (
                <li key={c.id}>
                  <div className="lg-card lg-card-hover px-3 py-2.5 flex items-center gap-3">
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                      style={{
                        background: 'rgba(139, 92, 246, 0.18)',
                        color: 'rgba(255, 255, 255, 0.9)',
                      }}
                    >
                      {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-[color:var(--lg-text-primary)] truncate">
                        {displayName}
                      </div>
                      {c.phone && (
                        <div className="text-[11px] text-[color:var(--lg-text-muted)] font-mono tabular-nums truncate">
                          {formatPhone(c.phone)}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => c.phone && onDial(c.phone)}
                      aria-label={`Call ${displayName}`}
                      className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-transform hover:scale-105 active:scale-95"
                      style={{
                        background:
                          'linear-gradient(135deg, #00d4ff 0%, #8b5cf6 55%, #ec4899 100%)',
                      }}
                    >
                      <Phone className="h-4 w-4 text-white" />
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
