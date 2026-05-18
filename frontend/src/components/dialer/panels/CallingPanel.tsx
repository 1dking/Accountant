import { PhoneOff } from 'lucide-react'
import type { DialerMode } from '../hooks/useTwilioDevice'

export default function CallingPanel({
  target,
  mode,
  onHangup,
}: {
  target: string
  mode: DialerMode
  onHangup: () => void
}) {
  return (
    <div className="px-6 py-8 space-y-6">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider text-[color:var(--lg-text-secondary)]">
          {mode === 'requesting-mic' ? 'Requesting microphone…' : 'Calling'}
        </div>
        <div className="font-mono text-2xl mt-3 text-[color:var(--lg-text-primary)] tabular-nums">
          {target}
        </div>
        <div className="text-sm text-[color:var(--lg-text-secondary)] mt-3 lg-breathing">
          {mode === 'requesting-mic' ? 'Allow microphone access if prompted' : 'Ringing…'}
        </div>
      </div>
      <button
        onClick={onHangup}
        className="w-full h-12 rounded-xl bg-red-600/90 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-600 transition-colors"
      >
        <PhoneOff className="h-5 w-5" />
        Cancel
      </button>
    </div>
  )
}
