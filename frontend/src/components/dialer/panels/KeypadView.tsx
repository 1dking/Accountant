/**
 * The keypad surface — number display, 3x4 keypad, gradient Call
 * button. Promoted to a top-level body for commit 1 (no tabs yet);
 * commit 2 will wrap this inside a KeypadTab next to Recents +
 * Contacts.
 *
 * Pure presentational — receives state + handlers via props. The
 * Twilio device lifecycle lives in useTwilioDevice; this component
 * just paints the controls.
 */
import { Delete, PhoneCall } from 'lucide-react'
import { cn } from '@/lib/utils'

const DIALPAD = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

interface Props {
  number: string
  setNumber: (n: string) => void
  onDigit: (digit: string) => void
  onBackspace: () => void
  onCall: () => void
  inputRef?: React.RefObject<HTMLInputElement | null>
  disabled: boolean
}

export default function KeypadView({
  number,
  setNumber,
  onDigit,
  onBackspace,
  onCall,
  inputRef,
  disabled,
}: Props) {
  return (
    <div className="flex flex-col gap-5 px-6 py-6">
      {/* Number display */}
      <div className="lg-card flex items-center gap-2 px-4 py-3">
        <input
          ref={inputRef}
          value={number}
          onChange={(e) => setNumber(e.target.value.replace(/[^0-9+*#() -]/g, ''))}
          placeholder="Enter number"
          aria-label="Phone number"
          className="flex-1 bg-transparent text-xl font-mono tabular-nums text-[color:var(--lg-text-primary)] placeholder:text-[color:var(--lg-text-muted)] outline-none text-center tracking-wider"
          disabled={disabled}
        />
        {number && (
          <button
            onClick={onBackspace}
            aria-label="Delete last digit"
            className="p-1.5 text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)] rounded-md"
          >
            <Delete className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* 3x4 keypad */}
      <div className="grid grid-cols-3 gap-2.5">
        {DIALPAD.flat().map((digit) => (
          <button
            key={digit}
            onClick={() => onDigit(digit)}
            disabled={disabled}
            aria-label={`Dial ${digit}`}
            className="lg-key h-14 rounded-xl text-xl font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {digit}
          </button>
        ))}
      </div>

      {/* Call button */}
      <button
        onClick={onCall}
        disabled={disabled || !number.trim()}
        className={cn(
          'lg-call-button w-full h-14 rounded-xl flex items-center justify-center gap-2',
          'text-base font-semibold tracking-wide',
        )}
      >
        <PhoneCall className="h-5 w-5" />
        {disabled ? 'Connecting…' : 'Call'}
      </button>
    </div>
  )
}
