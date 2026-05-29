/**
 * PreJoinGate — Commit 10. Pre-meeting device check + (when the
 * meeting is set to record) explicit recording-consent banner.
 *
 * Wraps LiveKit's `<PreJoin>` component (camera preview + device
 * pickers + mic/cam toggle + name field). After the user clicks
 * "Continue", if record_meeting=true, we intercept and show a
 * legal-compliance consent overlay. They must explicitly check
 * "I understand" before joining.
 *
 * The host flow (MeetingRoomPage) and admitted-guest flow
 * (MeetingJoinPage) both go through this gate before
 * connecting to <LiveKitRoom>.
 */
import { useState } from 'react'
import { PreJoin, type LocalUserChoices } from '@livekit/components-react'
import { Circle, ShieldCheck } from 'lucide-react'

export interface Props {
  recordMeeting: boolean
  defaultUserName?: string
  meetingTitle?: string
  onJoin: (choices: LocalUserChoices) => void
}

export default function PreJoinGate({
  recordMeeting, defaultUserName, meetingTitle, onJoin,
}: Props) {
  const [pendingChoices, setPendingChoices] = useState<LocalUserChoices | null>(null)
  const [consentChecked, setConsentChecked] = useState(false)

  const handleSubmit = (vals: LocalUserChoices) => {
    if (recordMeeting) {
      // Capture device choices, then make the user explicitly consent
      // before we connect to the room. Compliance-grade for record-on
      // meetings — accountant + legal verticals expect this gate.
      setPendingChoices(vals)
      return
    }
    onJoin(vals)
  }

  const handleConsent = () => {
    if (pendingChoices) onJoin(pendingChoices)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f1320', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 640 }}>
        {meetingTitle && (
          <div style={{ textAlign: 'center', marginBottom: 18 }}>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: 'white', margin: 0 }}>
              {meetingTitle}
            </h1>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', marginTop: 6 }}>
              Check your camera + mic before you join
            </p>
          </div>
        )}

        {/* LiveKit's PreJoin handles the entire device-check UX:
            camera preview, mic/cam toggles, device pickers, name field.
            We just style its container + intercept onSubmit. */}
        <div style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 16,
          overflow: 'hidden',
        }}>
          <PreJoin
            defaults={{ username: defaultUserName || '' }}
            onSubmit={handleSubmit}
            joinLabel={recordMeeting ? 'Review & join' : 'Join now'}
            persistUserChoices={true}
            data-lk-theme="default"
          />
        </div>

        {recordMeeting && (
          <p style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            marginTop: 12, fontSize: 12, color: 'rgba(252, 165, 165, 0.85)',
          }}>
            <Circle className="h-3 w-3" style={{ fill: '#dc2626', color: '#dc2626' }} />
            This meeting is set to be recorded.
          </p>
        )}
      </div>

      {pendingChoices && recordMeeting && (
        <ConsentOverlay
          checked={consentChecked}
          onCheckedChange={setConsentChecked}
          onAccept={handleConsent}
          onCancel={() => { setPendingChoices(null); setConsentChecked(false) }}
        />
      )}
    </div>
  )
}


function ConsentOverlay({
  checked, onCheckedChange, onAccept, onCancel,
}: {
  checked: boolean
  onCheckedChange: (v: boolean) => void
  onAccept: () => void
  onCancel: () => void
}) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(8, 10, 20, 0.78)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 480,
          background: '#101424',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 16,
          boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
          padding: 28, color: 'white',
        }}
      >
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px', marginBottom: 14,
          background: 'rgba(220, 38, 38, 0.18)',
          border: '1px solid rgba(220, 38, 38, 0.45)',
          borderRadius: 999, color: '#fecaca',
          fontSize: 11, fontWeight: 500, letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}>
          <ShieldCheck className="h-3 w-3" />
          Recording consent
        </div>

        <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 600 }}>
          This meeting will be recorded
        </h2>
        <p style={{ margin: '0 0 16px', fontSize: 13.5, color: 'rgba(255,255,255,0.72)', lineHeight: 1.55 }}>
          The host has enabled recording for this meeting. Both audio and
          video of everyone in the room are captured by the server and stored
          securely. The host can later transcribe and summarize it.
        </p>

        <label
          style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            padding: '12px 14px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => onCheckedChange(e.target.checked)}
            style={{ marginTop: 3, accentColor: '#6366f1' }}
          />
          <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.88)', lineHeight: 1.45 }}>
            I understand this meeting is being recorded and I consent to my
            video and audio being captured and stored.
          </span>
        </label>

        <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '8px 16px', fontSize: 13, fontWeight: 500,
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: 8, color: 'rgba(255,255,255,0.78)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onAccept}
            disabled={!checked}
            style={{
              padding: '8px 16px', fontSize: 13, fontWeight: 600,
              background: checked
                ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                : 'rgba(99, 102, 241, 0.25)',
              border: 'none', borderRadius: 8, color: 'white',
              cursor: checked ? 'pointer' : 'not-allowed',
              opacity: checked ? 1 : 0.6,
            }}
          >
            Join meeting
          </button>
        </div>
      </div>
    </div>
  )
}
