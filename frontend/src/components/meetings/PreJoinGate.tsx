/**
 * PreJoinGate — simplified post-bug-hunt version.
 *
 * The previous implementation wrapped LiveKit's `<PreJoin>` component
 * (camera preview + device pickers + mic/cam toggles + name field).
 * It produced a tangled getUserMedia lifecycle: PreJoin would acquire
 * the camera for its preview, the user would click Join, the
 * LocalUserChoices it emitted would conflict with the next
 * getUserMedia call inside LiveKitRoom, and tracks would publish
 * already-muted. Browser permissions panel showed "Camera: Using now"
 * + a silhouette tile. Removing PostConnectMuteSync didn't fix it
 * either, so the suspect is PreJoin itself.
 *
 * New behavior: no device preview. Just a name field + a Join button.
 * When record_meeting=true, the consent overlay still gates the join.
 * The actual media acquisition happens inside <LiveKitRoom> with
 * audio={true}/video={true}, and the toolbar toggles control mute
 * state from there. If users want a device picker later, we add it
 * inside the room (it can be hung off the toolbar) — without
 * pre-acquiring media before the room mounts.
 */
import { useState } from 'react'
import { type LocalUserChoices } from '@livekit/components-react'
import { Loader2, ShieldCheck, Video as VideoIcon, Mic as MicIcon } from 'lucide-react'
import { usePublicBranding } from '@/hooks/useBranding'

export interface Props {
  recordMeeting: boolean
  defaultUserName?: string
  meetingTitle?: string
  onJoin: (choices: LocalUserChoices) => void
}

export default function PreJoinGate({
  recordMeeting, defaultUserName, meetingTitle, onJoin,
}: Props) {
  const [name, setName] = useState(defaultUserName || '')
  const [showConsent, setShowConsent] = useState(false)
  const [consentChecked, setConsentChecked] = useState(false)
  const [joining, setJoining] = useState(false)
  const { logoUrl, orgName } = usePublicBranding()

  // LocalUserChoices that drive LiveKitRoom — we always go in with
  // mic+cam ON. The actual media acquisition is LK's responsibility
  // once the room mounts. deviceId omitted → LK picks OS default.
  const choices: LocalUserChoices = {
    username: name,
    audioEnabled: true,
    videoEnabled: true,
    audioDeviceId: '',
    videoDeviceId: '',
  }

  const submit = () => {
    if (recordMeeting) {
      setShowConsent(true)
      return
    }
    setJoining(true)
    onJoin(choices)
  }

  const accept = () => {
    setJoining(true)
    onJoin(choices)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f1320', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 460 }}>
        {logoUrl && (
          <div style={{ textAlign: 'center', marginBottom: 18 }}>
            <img
              src={logoUrl}
              alt={orgName}
              style={{ maxHeight: 44, objectFit: 'contain', display: 'inline-block' }}
            />
          </div>
        )}
        {meetingTitle && (
          <div style={{ textAlign: 'center', marginBottom: 22 }}>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: 'white', margin: 0 }}>
              {meetingTitle}
            </h1>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', marginTop: 6 }}>
              You'll join with your camera and microphone on. Use the toolbar to mute once you're in.
            </p>
          </div>
        )}

        <div style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 16,
          padding: 24,
        }}>
          {defaultUserName === undefined && (
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'rgba(255,255,255,0.65)', marginBottom: 6 }}>
                Your name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Smith"
                autoFocus
                style={{
                  width: '100%', padding: '10px 12px', fontSize: 14,
                  background: 'rgba(0,0,0,0.35)', color: 'white',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8, outline: 'none',
                }}
              />
            </div>
          )}

          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '10px 12px', marginBottom: 16,
            background: 'rgba(99,102,241,0.08)',
            border: '1px solid rgba(99,102,241,0.18)',
            borderRadius: 10,
            fontSize: 13, color: 'rgba(255,255,255,0.78)',
          }}>
            <MicIcon className="h-4 w-4" />
            <VideoIcon className="h-4 w-4" />
            <span>Microphone &amp; camera will start enabled.</span>
          </div>

          <button
            onClick={submit}
            disabled={joining || (defaultUserName === undefined && !name.trim())}
            style={{
              width: '100%', padding: '12px 16px', fontSize: 14, fontWeight: 600,
              background: (joining || (defaultUserName === undefined && !name.trim()))
                ? 'rgba(99,102,241,0.35)'
                : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, color: 'white',
              cursor: (joining || (defaultUserName === undefined && !name.trim())) ? 'not-allowed' : 'pointer',
              opacity: (joining || (defaultUserName === undefined && !name.trim())) ? 0.6 : 1,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
          >
            {joining && <Loader2 className="h-4 w-4 animate-spin" />}
            {recordMeeting ? 'Review & join' : 'Join meeting'}
          </button>
        </div>

        {recordMeeting && (
          <p style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            marginTop: 12, fontSize: 12, color: 'rgba(252, 165, 165, 0.85)',
          }}>
            <ShieldCheck className="h-3 w-3" />
            This meeting is set to be recorded.
          </p>
        )}
      </div>

      {showConsent && (
        <ConsentOverlay
          checked={consentChecked}
          onCheckedChange={setConsentChecked}
          onAccept={accept}
          onCancel={() => { setShowConsent(false); setConsentChecked(false) }}
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
