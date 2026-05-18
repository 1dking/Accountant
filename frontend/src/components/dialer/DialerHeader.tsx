/**
 * Persistent header at the top of the dialer drawer. Shows the
 * user's assigned Twilio number ("Calling From {number}") with a
 * small wave indicator that animates when idle and goes solid
 * during active calls.
 *
 * Phone-number resolution: prefers the user's assigned_phone_number
 * (set by admin team management). If multiple numbers are assigned,
 * we just show the first; multi-number dropdown is deferred to a
 * follow-up since most users have one assignment.
 */
import { Phone, X } from 'lucide-react'
import type { DialerMode } from './hooks/useTwilioDevice'

function formatPhone(raw: string | null | undefined): string {
  if (!raw) return ''
  // North-American format: +1 (xxx) xxx-xxxx → keep our internal
  // string display compact. Falls back to the raw input if it doesn't
  // match the pattern.
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 11 && digits.startsWith('1')) {
    const a = digits.slice(1, 4)
    const b = digits.slice(4, 7)
    const c = digits.slice(7, 11)
    return `(${a}) ${b}-${c}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  }
  return raw
}

export default function DialerHeader({
  callingFrom,
  mode,
  onClose,
}: {
  callingFrom: string | null
  mode: DialerMode
  onClose: () => void
}) {
  const isActive = mode === 'in-call' || mode === 'incoming-ringing'

  return (
    <header className="flex items-center justify-between px-5 py-4 border-b border-white/10 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <Phone className="h-4 w-4 text-[color:var(--lg-text-secondary)] shrink-0" />
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-[color:var(--lg-text-muted)] leading-none mb-1">
            Calling from
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono tabular-nums text-[color:var(--lg-text-primary)] truncate">
              {callingFrom ? formatPhone(callingFrom) : 'No number assigned'}
            </span>
            <WaveBars active={isActive} />
          </div>
        </div>
      </div>
      <button
        onClick={onClose}
        aria-label="Close dialer"
        className="p-1.5 rounded-md text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)] hover:bg-white/8 transition-colors shrink-0"
      >
        <X className="h-4 w-4" />
      </button>
    </header>
  )
}

/**
 * Three small bars that animate vertically. When active=true, the
 * bars freeze at full height (in-call solid indicator). When idle,
 * they breathe at ~1s loop.
 */
function WaveBars({ active }: { active: boolean }) {
  return (
    <div className="flex items-end gap-0.5 h-3" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={active ? 'h-full' : 'lg-wave-bar h-full'}
          style={{
            width: 2,
            background: active
              ? 'rgb(52 211 153)' /* emerald-400 */
              : 'rgba(255, 255, 255, 0.45)',
            borderRadius: 1,
          }}
        />
      ))}
    </div>
  )
}
