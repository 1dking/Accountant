/**
 * Recents tab — last 50 calls (inbound + outbound) with contact-name
 * resolution against the contacts list. Tap row → redial via the
 * Twilio device.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Phone, PhoneIncoming, PhoneMissed, PhoneOutgoing } from 'lucide-react'
import { cn, formatRelativeTime } from '@/lib/utils'
import { listCalls } from '@/api/communication'
import { listContacts } from '@/api/contacts'
import type { CallLogEntry, Contact } from '@/types/models'

function initialsFor(name: string | null | undefined, fallback: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/)
    return (parts[0]?.[0] || '') + (parts[1]?.[0] || '')
  }
  return fallback
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

export default function RecentsTab({ onDial }: Props) {
  const callsQuery = useQuery({
    queryKey: ['dialer-recents'],
    queryFn: () => listCalls({ page_size: 50 }),
  })
  // Pull a generous slice of contacts so we can resolve names for
  // recent callers. 200 covers the realistic working set; if a contact
  // is beyond it, the row falls back to the raw phone number.
  const contactsQuery = useQuery({
    queryKey: ['dialer-contacts-index'],
    queryFn: () => listContacts({ page_size: 200 }),
  })

  const calls: CallLogEntry[] = callsQuery.data?.data || []
  const contacts: Contact[] = (contactsQuery.data?.data as Contact[]) || []

  // Build a contact-by-id index AND a contact-by-phone fallback so
  // calls without a contact_id (cold leads) still resolve when the
  // phone is in the contact list.
  const { byId, byPhone } = useMemo(() => {
    const byIdMap = new Map<string, Contact>()
    const byPhoneMap = new Map<string, Contact>()
    for (const c of contacts) {
      byIdMap.set(c.id, c)
      if (c.phone) {
        // Normalize to digits-only so different formatting still
        // matches across the boundary.
        byPhoneMap.set(c.phone.replace(/\D/g, ''), c)
      }
    }
    return { byId: byIdMap, byPhone: byPhoneMap }
  }, [contacts])

  if (callsQuery.isLoading || contactsQuery.isLoading) {
    return (
      <div className="px-6 py-8 text-sm text-[color:var(--lg-text-muted)]">
        Loading recent calls…
      </div>
    )
  }

  if (calls.length === 0) {
    return (
      <div className="px-6 py-12 text-center">
        <Phone className="h-8 w-8 mx-auto text-[color:var(--lg-text-muted)] mb-3" />
        <p className="text-sm text-[color:var(--lg-text-secondary)]">No recent calls</p>
        <p className="text-xs text-[color:var(--lg-text-muted)] mt-1">
          Use the Keypad to make your first call.
        </p>
      </div>
    )
  }

  return (
    <ul className="px-3 py-3 space-y-1.5">
      {calls.map((call) => {
        const otherNumber = call.direction === 'inbound' ? call.from_number : call.to_number
        const matched =
          (call.contact_id && byId.get(call.contact_id)) ||
          byPhone.get(otherNumber.replace(/\D/g, '')) ||
          null
        const displayName = matched?.contact_name || matched?.company_name || null
        const fallbackInitials = call.direction === 'inbound' ? 'UC' : '?'

        return (
          <li key={call.id}>
            <button
              onClick={() => onDial(otherNumber)}
              className={cn(
                'lg-card lg-card-hover w-full text-left px-3 py-2.5 flex items-center gap-3',
              )}
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                style={{
                  background: 'rgba(139, 92, 246, 0.18)',
                  color: 'rgba(255, 255, 255, 0.9)',
                }}
              >
                {initialsFor(displayName, fallbackInitials).toUpperCase().slice(0, 2)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <DirectionIcon
                    direction={call.direction}
                    status={call.status}
                  />
                  <span className="text-sm text-[color:var(--lg-text-primary)] truncate">
                    {displayName || formatPhone(otherNumber)}
                  </span>
                </div>
                {displayName && (
                  <div className="text-[11px] text-[color:var(--lg-text-muted)] font-mono tabular-nums truncate">
                    {formatPhone(otherNumber)}
                  </div>
                )}
              </div>
              <div className="text-[11px] text-[color:var(--lg-text-muted)] shrink-0 tabular-nums">
                {formatRelativeTime(call.created_at)}
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function DirectionIcon({
  direction,
  status,
}: {
  direction: string
  status: string
}) {
  const isMissed =
    direction === 'inbound' && (status === 'no-answer' || status === 'missed' || status === 'failed')

  if (isMissed) {
    return <PhoneMissed className="h-3.5 w-3.5 text-red-400 shrink-0" />
  }
  if (direction === 'inbound') {
    return <PhoneIncoming className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
  }
  return <PhoneOutgoing className="h-3.5 w-3.5 text-blue-400 shrink-0" />
}
