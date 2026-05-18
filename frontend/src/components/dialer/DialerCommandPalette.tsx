/**
 * Inline command palette at the top of the dialer drawer.
 *
 * Uses cmdk for keyboard nav + filtering primitives. Filters across
 * three sources:
 *   - Contacts (name + company + phone digits)
 *   - Recents (caller name resolved against contacts, plus raw phone
 *     digits)
 *   - Raw-number dial: when the input looks dialable (≥7 digits),
 *     we surface a "Dial <number>" action at the top.
 *
 * Keyboard:
 *   - Cmd+K (Mac) / Ctrl+K (anything else) focuses the input from
 *     anywhere in the drawer
 *   - Esc clears the input (does NOT close the drawer — that's
 *     handled by the parent's global Escape listener which still
 *     wins when the input is empty)
 *   - ↑ ↓ + Enter — built-in cmdk behavior
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Command } from 'cmdk'
import { Phone, PhoneCall, Search, User } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { listCalls } from '@/api/communication'
import { listContacts } from '@/api/contacts'
import type { CallLogEntry, Contact } from '@/types/models'

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

export default function DialerCommandPalette({ onDial }: Props) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Cmd+K / Ctrl+K globally focuses the input. Listener lives here so
  // the palette owns its own shortcut — moving the palette to another
  // surface doesn't require rewiring keymap glue elsewhere.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isModK = (e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')
      if (isModK) {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const contactsQuery = useQuery({
    queryKey: ['dialer-contacts-list'],
    queryFn: () => listContacts({ page_size: 200 }),
    staleTime: 60_000,
  })

  const callsQuery = useQuery({
    queryKey: ['dialer-recents'],
    queryFn: () => listCalls({ page_size: 50 }),
    staleTime: 30_000,
  })

  const contacts: Contact[] = (contactsQuery.data?.data as Contact[]) || []
  const calls: CallLogEntry[] = callsQuery.data?.data || []

  const trimmed = query.trim()
  const queryDigits = trimmed.replace(/\D/g, '')
  const looksDialable = queryDigits.length >= 7

  // Filter the lists ourselves (cmdk's built-in filter only sees the
  // item value — we want substring match on multiple fields per item).
  const filteredContacts = useMemo(() => {
    if (!trimmed) return contacts.filter((c) => c.phone).slice(0, 6)
    const q = trimmed.toLowerCase()
    return contacts
      .filter((c) => c.phone)
      .filter((c) => {
        if (c.contact_name?.toLowerCase().includes(q)) return true
        if (c.company_name?.toLowerCase().includes(q)) return true
        if (queryDigits && c.phone?.replace(/\D/g, '').includes(queryDigits)) return true
        return false
      })
      .slice(0, 6)
  }, [contacts, trimmed, queryDigits])

  const filteredCalls = useMemo(() => {
    if (!trimmed) return calls.slice(0, 4)
    const q = trimmed.toLowerCase()
    return calls
      .filter((call) => {
        const other = call.direction === 'inbound' ? call.from_number : call.to_number
        if (queryDigits && other.replace(/\D/g, '').includes(queryDigits)) return true
        // Try to resolve a name via the contact list for substring matching.
        const matched = contacts.find((c) => c.id === call.contact_id)
        if (matched?.contact_name?.toLowerCase().includes(q)) return true
        if (matched?.company_name?.toLowerCase().includes(q)) return true
        return false
      })
      .slice(0, 4)
  }, [calls, contacts, trimmed, queryDigits])

  const handleDialAndClear = (number: string) => {
    setQuery('')
    onDial(number)
  }

  return (
    <Command
      shouldFilter={false}
      className="border-b border-white/10 shrink-0"
      label="Dialer command palette"
    >
      <div className="px-5 pt-3 pb-3">
        <div className="lg-card flex items-center gap-2 px-3 py-2">
          <Search className="h-4 w-4 text-[color:var(--lg-text-muted)] shrink-0" />
          <Command.Input
            ref={inputRef}
            value={query}
            onValueChange={setQuery}
            placeholder="Search contacts or dial number…   ⌘K"
            className="flex-1 bg-transparent text-sm text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-muted)] outline-none"
          />
        </div>
      </div>

      {trimmed && (
        <Command.List className="max-h-72 overflow-y-auto px-3 pb-3 space-y-1">
          {looksDialable && (
            <Command.Item
              value={`dial-${queryDigits}`}
              onSelect={() => handleDialAndClear(trimmed)}
              className="lg-card lg-card-hover px-3 py-2.5 flex items-center gap-3 cursor-pointer aria-selected:bg-white/10"
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                style={{ background: 'linear-gradient(135deg, #00d4ff, #8b5cf6, #ec4899)' }}
              >
                <PhoneCall className="h-4 w-4 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-[color:var(--lg-text-primary)]">
                  Dial <span className="font-mono tabular-nums">{formatPhone(trimmed)}</span>
                </div>
              </div>
            </Command.Item>
          )}

          {filteredContacts.length > 0 && (
            <Command.Group heading="Contacts" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-[color:var(--lg-text-muted)]">
              {filteredContacts.map((c) => {
                const name = c.contact_name || c.company_name
                return (
                  <Command.Item
                    key={`contact-${c.id}`}
                    value={`contact-${c.id}`}
                    onSelect={() => c.phone && handleDialAndClear(c.phone)}
                    className="lg-card lg-card-hover px-3 py-2.5 flex items-center gap-3 cursor-pointer aria-selected:bg-white/10"
                  >
                    <User className="h-4 w-4 text-[color:var(--lg-text-secondary)] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-[color:var(--lg-text-primary)] truncate">{name}</div>
                      {c.phone && (
                        <div className="text-[11px] text-[color:var(--lg-text-muted)] font-mono tabular-nums truncate">
                          {formatPhone(c.phone)}
                        </div>
                      )}
                    </div>
                  </Command.Item>
                )
              })}
            </Command.Group>
          )}

          {filteredCalls.length > 0 && (
            <Command.Group heading="Recents" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-[color:var(--lg-text-muted)]">
              {filteredCalls.map((call) => {
                const other = call.direction === 'inbound' ? call.from_number : call.to_number
                const matched = contacts.find((c) => c.id === call.contact_id)
                const display = matched?.contact_name || matched?.company_name || formatPhone(other)
                return (
                  <Command.Item
                    key={`recent-${call.id}`}
                    value={`recent-${call.id}`}
                    onSelect={() => handleDialAndClear(other)}
                    className="lg-card lg-card-hover px-3 py-2.5 flex items-center gap-3 cursor-pointer aria-selected:bg-white/10"
                  >
                    <Phone className="h-4 w-4 text-[color:var(--lg-text-secondary)] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-[color:var(--lg-text-primary)] truncate">{display}</div>
                      <div className="text-[11px] text-[color:var(--lg-text-muted)] font-mono tabular-nums truncate">
                        {formatPhone(other)}
                      </div>
                    </div>
                  </Command.Item>
                )
              })}
            </Command.Group>
          )}

          <Command.Empty className="px-3 py-4 text-xs text-[color:var(--lg-text-muted)] text-center">
            {looksDialable
              ? null
              : 'No matches — try a contact name, company, or phone number.'}
          </Command.Empty>
        </Command.List>
      )}
    </Command>
  )
}
