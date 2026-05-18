import { Mic, MicOff, PhoneOff } from 'lucide-react'
import { cn } from '@/lib/utils'

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
}: {
  remoteNumber: string
  durationSeconds: number
  isMuted: boolean
  onMute: () => void
  onHangup: () => void
}) {
  return (
    <div className="px-6 py-8 space-y-6">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider text-emerald-400/80">
          In call
        </div>
        <div className="font-mono text-2xl mt-3 text-[color:var(--lg-text-primary)] tabular-nums">
          {remoteNumber}
        </div>
        <div className="text-sm text-emerald-400 mt-2 font-mono tabular-nums">
          {formatDuration(durationSeconds)}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onMute}
          className={cn(
            'h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition-colors',
            isMuted
              ? 'bg-white/14 text-white'
              : 'bg-white/6 text-white/80 hover:bg-white/10',
          )}
        >
          {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          {isMuted ? 'Unmute' : 'Mute'}
        </button>
        <button
          onClick={onHangup}
          className="h-12 rounded-xl bg-red-600/90 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-600 transition-colors"
        >
          <PhoneOff className="h-5 w-5" />
          Hang Up
        </button>
      </div>
    </div>
  )
}
