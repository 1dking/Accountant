import { useState } from 'react'
import { Delete, Grid3x3, Mic, MicOff, PhoneOff } from 'lucide-react'
import { cn } from '@/lib/utils'

const DTMF = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function InCallPanel({
  remoteNumber,
  durationSeconds,
  isMuted,
  onMute,
  onHangup,
  onSendDigits,
}: {
  remoteNumber: string
  durationSeconds: number
  isMuted: boolean
  onMute: () => void
  onHangup: () => void
  /** Send a DTMF touch-tone on the LIVE call (for IVR prompts, PINs, extensions). */
  onSendDigits: (digit: string) => void
}) {
  const [showKeypad, setShowKeypad] = useState(false)
  const [entered, setEntered] = useState('')

  const press = (digit: string) => {
    onSendDigits(digit) // fire the DTMF tone down the active call
    setEntered((e) => (e + digit).slice(-32))
  }

  return (
    <div className="px-6 py-8 space-y-6">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider text-emerald-400/80 inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="lg-breathing inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"
          />
          In call
        </div>
        <div className="font-mono text-2xl mt-3 text-[color:var(--lg-text-primary)] tabular-nums">
          {remoteNumber}
        </div>
        <div className="text-sm text-emerald-400 mt-2 font-mono tabular-nums">
          {formatDuration(durationSeconds)}
        </div>
      </div>

      {/* In-call DTMF keypad — revealed with the Keypad button below. Because
          InCallPanel only renders during a live call and each press goes
          straight to the active Call's sendDigits, the keypad is usable exactly
          when you need it: answering "enter your number", PINs, extensions. */}
      {showKeypad && (
        <div className="space-y-3">
          <div className="lg-card flex items-center justify-center gap-2 px-4 py-2.5 min-h-[2.75rem]">
            <span className="flex-1 text-center font-mono text-lg tabular-nums tracking-widest text-[color:var(--lg-text-primary)]">
              {entered || (
                <span className="text-[color:var(--lg-text-muted)]">Tap to enter digits</span>
              )}
            </span>
            {entered && (
              <button
                onClick={() => setEntered('')}
                aria-label="Clear entered digits"
                className="p-1.5 text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)] rounded-md"
              >
                <Delete className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2.5">
            {DTMF.flat().map((digit) => (
              <button
                key={digit}
                onClick={() => press(digit)}
                aria-label={`Send ${digit}`}
                className="lg-key h-14 rounded-xl text-xl font-medium"
              >
                {digit}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onMute}
          className={cn(
            'h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition-colors',
            isMuted ? 'bg-white/14 text-white' : 'bg-white/6 text-white/80 hover:bg-white/10',
          )}
        >
          {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          {isMuted ? 'Unmute' : 'Mute'}
        </button>
        <button
          onClick={() => setShowKeypad((v) => !v)}
          aria-pressed={showKeypad}
          className={cn(
            'h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition-colors',
            showKeypad ? 'bg-white/14 text-white' : 'bg-white/6 text-white/80 hover:bg-white/10',
          )}
        >
          <Grid3x3 className="h-5 w-5" />
          Keypad
        </button>
      </div>
      <button
        onClick={onHangup}
        className="w-full h-12 rounded-xl bg-red-600/90 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-600 transition-colors"
      >
        <PhoneOff className="h-5 w-5" />
        Hang Up
      </button>
    </div>
  )
}
