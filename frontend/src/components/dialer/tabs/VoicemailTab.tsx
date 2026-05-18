import { Mail } from 'lucide-react'

export default function VoicemailTab() {
  return (
    <div className="px-6 py-12 text-center space-y-4">
      <div
        className="w-14 h-14 rounded-2xl mx-auto flex items-center justify-center"
        style={{
          background:
            'linear-gradient(135deg, rgba(0,212,255,0.16), rgba(139,92,246,0.16))',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <Mail className="h-6 w-6 text-[color:var(--lg-text-secondary)]" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-[color:var(--lg-text-primary)]">
          Voicemail inbox — coming in Phase B
        </h3>
        <p className="text-xs text-[color:var(--lg-text-secondary)] mt-2 max-w-[300px] mx-auto leading-relaxed">
          Visual list of voicemails with inline transcripts and audio
          playback, unread badges, and a per-message review queue —
          surfaced in this tab so you never miss a callback waiting
          for you in the Call Log.
        </p>
      </div>
    </div>
  )
}
