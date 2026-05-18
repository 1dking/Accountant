import { PhoneCall, PhoneIncoming, PhoneOff } from 'lucide-react'

export default function IncomingPanel({
  fromNumber,
  onAccept,
  onReject,
}: {
  fromNumber: string | null
  onAccept: () => void
  onReject: () => void
}) {
  return (
    <div className="px-6 py-8 space-y-6">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider lg-breathing inline-flex items-center gap-1.5 text-[color:var(--lg-text-secondary)]">
          <PhoneIncoming className="h-3.5 w-3.5" />
          Incoming call
        </div>
        <div className="font-mono text-2xl mt-3 text-[color:var(--lg-text-primary)] tabular-nums">
          {fromNumber || 'Unknown'}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onReject}
          className="h-12 rounded-xl bg-red-600/90 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-600 transition-colors"
        >
          <PhoneOff className="h-5 w-5" />
          Reject
        </button>
        <button
          onClick={onAccept}
          className="h-12 rounded-xl bg-emerald-500/90 text-white font-medium flex items-center justify-center gap-2 hover:bg-emerald-500 transition-colors"
        >
          <PhoneCall className="h-5 w-5" />
          Accept
        </button>
      </div>
    </div>
  )
}
