/**
 * The phone-icon button in the app header. Opens the dialer drawer
 * and reflects the live Twilio state via icon tint + ringing pulse.
 */
import { Phone } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DialerMode } from './hooks/useTwilioDevice'

function iconColorClass(mode: DialerMode): string {
  switch (mode) {
    case 'ready':
      return 'text-emerald-500'
    case 'incoming-ringing':
      return 'text-blue-400'
    case 'in-call':
      return 'text-emerald-400'
    case 'permission-denied':
    case 'error':
      return 'text-red-500'
    default:
      return 'text-gray-400 dark:text-gray-500'
  }
}

function tooltipForMode(
  mode: DialerMode,
  incomingNumber: string | null,
  errorMsg: string | null,
): string {
  switch (mode) {
    case 'idle':
    case 'initializing':
      return 'Phone (initializing…)'
    case 'ready':
      return 'Phone (ready)'
    case 'incoming-ringing':
      return incomingNumber ? `Incoming call from ${incomingNumber}` : 'Incoming call'
    case 'outgoing-connecting':
    case 'requesting-mic':
      return 'Calling…'
    case 'in-call':
      return 'Call in progress'
    case 'permission-denied':
      return 'Microphone access needed'
    case 'error':
      return errorMsg || 'Phone error'
  }
}

export default function DialerTrigger({
  mode,
  incomingNumber,
  errorMsg,
  isOpen,
  onClick,
}: {
  mode: DialerMode
  incomingNumber: string | null
  errorMsg: string | null
  isOpen: boolean
  onClick: () => void
}) {
  const tooltip = tooltipForMode(mode, incomingNumber, errorMsg)
  return (
    <button
      onClick={onClick}
      title={tooltip}
      aria-label={tooltip}
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      className={cn(
        'relative p-2 rounded-lg transition-colors',
        isOpen
          ? 'bg-gray-100 dark:bg-gray-800'
          : 'hover:bg-gray-50 dark:hover:bg-gray-800',
      )}
    >
      <Phone className={cn('h-5 w-5', iconColorClass(mode))} />
      {mode === 'incoming-ringing' && (
        <span className="absolute inset-0 rounded-lg animate-ping bg-blue-400/20 pointer-events-none" />
      )}
    </button>
  )
}
