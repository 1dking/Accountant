/**
 * MeetingJoinPage — public route /m/:slug (Commit 8, restructured 25).
 *
 * Single-screen Google-Meet flow:
 *   1. Page loads → fetch public meeting info (title, host, record flag).
 *   2. Knock screen: name input + live camera/mic preview (via
 *      navigator.mediaDevices.getUserMedia) + recording consent banner
 *      when record_meeting=true.
 *   3. Click "Ask to join" → POST /knock → poll /lobby/{id}.
 *   4. On 'admitted', stop the preview stream and AUTO-mount LiveKitRoom
 *      with audio:true, video:true. No second click, no PreJoinGate.
 *
 * If the visitor is already authenticated AND owns this meeting, we
 * skip the email gate and redirect them to the host room view.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import {
  LiveKitRoom, LayoutContextProvider, GridLayout, ParticipantTile, RoomAudioRenderer,
  ControlBar, useTracks, useRoomContext,
} from '@livekit/components-react'
import '@livekit/components-styles'
import { Track, RoomEvent } from 'livekit-client'
import { Loader2, DoorOpen, Circle } from 'lucide-react'
import { usePublicBranding } from '@/hooks/useBranding'
import {
  getPublicMeetingInfo,
  knockAtLobby,
  pollLobbyStatus,
  type PublicMeetingInfo,
  type LobbyStatusPollResponse,
} from '@/api/meetings'

const LIVEKIT_URL =
  import.meta.env.VITE_LIVEKIT_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/meetings/livekit-proxy`

const POLL_MS = 2500

type Stage = 'loading' | 'knock' | 'waiting' | 'admitted' | 'denied' | 'ended' | 'not-found'

export default function MeetingJoinPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { logoUrl, orgName, branding } = usePublicBranding()
  const brandColor = branding?.primary_color || '#4f46e5'

  const [meeting, setMeeting] = useState<PublicMeetingInfo | null>(null)
  const [stage, setStage] = useState<Stage>('loading')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [knockError, setKnockError] = useState<string | null>(null)
  const [knockBusy, setKnockBusy] = useState(false)
  const [lobbyId, setLobbyId] = useState<string | null>(null)
  const [livekit, setLivekit] = useState<LobbyStatusPollResponse | null>(null)
  // Commit 25 — pre-room camera + recording-consent state. Replaces the
  // post-admit PreJoinGate.
  const [previewStream, setPreviewStream] = useState<MediaStream | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [recordingConsent, setRecordingConsent] = useState(false)
  const previewVideoRef = useRef<HTMLVideoElement | null>(null)

  // Step 1: load the public meeting info
  useEffect(() => {
    if (!slug) {
      setStage('not-found')
      return
    }
    getPublicMeetingInfo(slug)
      .then((res) => {
        setMeeting(res.data)
        setStage('knock')
      })
      .catch(() => setStage('not-found'))
  }, [slug])

  // Step 2: acquire camera + mic preview during the knock / waiting
  // stages. Stopped on stage='admitted' so the device handle is fully
  // released before LiveKitRoom acquires fresh tracks.
  useEffect(() => {
    if (stage !== 'knock' && stage !== 'waiting') return
    if (previewStream) return
    let cancelled = false
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: true })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop())
          return
        }
        setPreviewStream(s)
        setPreviewError(null)
      })
      .catch((e: any) => {
        if (cancelled) return
        setPreviewError(
          e?.name === 'NotAllowedError'
            ? 'Camera/microphone permission denied. You can still knock — host can admit you, but you may need to grant permission to be heard or seen.'
            : `Could not access camera/mic: ${e?.message || e?.name || 'unknown'}`,
        )
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage])

  // Bind the live MediaStream to the preview <video>.
  useEffect(() => {
    if (previewVideoRef.current && previewStream) {
      previewVideoRef.current.srcObject = previewStream
    }
  }, [previewStream])

  // On admit: stop the preview tracks (release device handle) BEFORE
  // LiveKitRoom mounts and asks for its own tracks. Avoids the
  // "publishing rejected" / "track muted on connect" race the LK
  // preview component used to trigger.
  useEffect(() => {
    if (stage !== 'admitted') return
    if (!previewStream) return
    previewStream.getTracks().forEach((t) => t.stop())
    setPreviewStream(null)
  }, [stage, previewStream])

  // Step 3-4: once we have a lobby_id, poll every 2.5 sec
  useEffect(() => {
    if (!lobbyId || !slug || stage !== 'waiting') return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const tick = async () => {
      try {
        const res = await pollLobbyStatus(slug, lobbyId)
        if (cancelled) return
        if (res.data.status === 'admitted' && res.data.token) {
          setLivekit(res.data)
          setStage('admitted')
          return
        }
        if (res.data.status === 'denied') {
          setStage('denied')
          return
        }
        if (res.data.status === 'ended') {
          setStage('ended')
          return
        }
        // 'waiting' → keep polling
        timer = setTimeout(tick, POLL_MS)
      } catch {
        // Backoff once on transient error then retry — common during
        // network blips on guest's connection.
        if (!cancelled) timer = setTimeout(tick, POLL_MS * 2)
      }
    }
    tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [lobbyId, slug, stage])

  const handleKnock = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!slug || !name.trim()) return
    if (meeting?.record_meeting && !recordingConsent) {
      setKnockError('Please confirm you consent to being recorded.')
      return
    }
    setKnockError(null)
    setKnockBusy(true)
    try {
      const res = await knockAtLobby(slug, name.trim(), email.trim())
      setLobbyId(res.data.lobby_id)
      setStage('waiting')
    } catch (err: any) {
      setKnockError(err?.message || 'Could not knock. Try again.')
    } finally {
      setKnockBusy(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (stage === 'loading') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-white" />
      </div>
    )
  }

  if (stage === 'not-found') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-gray-800 rounded-xl p-8 text-center">
          <h1 className="text-xl font-semibold text-white mb-2">Meeting not found</h1>
          <p className="text-sm text-gray-400 mb-6">
            This meeting link may have expired or been cancelled.
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg"
          >
            Back to home
          </button>
        </div>
      </div>
    )
  }

  if (stage === 'denied') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-gray-800 rounded-xl p-8 text-center">
          <h1 className="text-xl font-semibold text-white mb-2">Not admitted</h1>
          <p className="text-sm text-gray-400">
            The host declined to admit you. If this seems wrong, reach out
            to them directly.
          </p>
        </div>
      </div>
    )
  }

  if (stage === 'ended') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-gray-800 rounded-xl p-8 text-center">
          <h1 className="text-xl font-semibold text-white mb-2">This meeting has ended</h1>
          <p className="text-sm text-gray-400">Thanks for stopping by.</p>
        </div>
      </div>
    )
  }

  if (stage === 'admitted' && livekit?.token) {
    // Commit 25 — auto-mount the LiveKitRoom on admit. No PreJoinGate
    // between admit and join: the guest already entered their name,
    // granted camera/mic, and (if applicable) consented to recording
    // on the knock screen. They drop directly into the meeting.
    return (
      <div style={{ height: '100vh', background: '#111827' }}>
        <LiveKitRoom
          serverUrl={LIVEKIT_URL}
          token={livekit.token}
          connect={true}
          onDisconnected={() => navigate('/')}
          audio={true}
          video={true}
          data-lk-theme="default"
          style={{ height: '100%' }}
        >
          <LayoutContextProvider>
            <GuestForceEnableMediaOnConnect />
            <GuestStage />
          </LayoutContextProvider>
        </LiveKitRoom>
      </div>
    )
  }

  // Stage === 'knock' or 'waiting' — single screen with camera preview.
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-6 py-8">
      <div className="max-w-lg w-full">
        {logoUrl && (
          <div className="flex justify-center mb-5">
            <img
              src={logoUrl}
              alt={orgName}
              style={{ maxHeight: 44, objectFit: 'contain' }}
            />
          </div>
        )}
        <div className="bg-gray-800 rounded-xl shadow-2xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="h-10 w-10 rounded-full bg-indigo-500/20 border border-indigo-400/40 flex items-center justify-center">
              <DoorOpen className="h-5 w-5 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white leading-tight">
                {meeting?.title || 'Meeting'}
              </h1>
              {meeting?.host_name && (
                <p className="text-xs text-gray-400 mt-0.5">Hosted by {meeting.host_name}</p>
              )}
            </div>
          </div>

          {/* Live camera preview — always shown on knock + waiting so
              the guest can see how they look before being admitted. */}
          <div
            className="mb-4 rounded-lg overflow-hidden bg-black flex items-center justify-center"
            style={{ aspectRatio: '16 / 9' }}
          >
            {previewStream ? (
              <video
                ref={previewVideoRef}
                autoPlay
                playsInline
                muted
                style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
              />
            ) : previewError ? (
              <div className="text-center px-6 py-8">
                <p className="text-xs text-amber-300">{previewError}</p>
              </div>
            ) : (
              <Loader2 className="h-6 w-6 animate-spin text-gray-500" />
            )}
          </div>

          {/* Recording notice — when the meeting is set to record,
              the guest must explicitly consent BEFORE knocking. */}
          {meeting?.record_meeting && (
            <div
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '12px 14px', marginBottom: 12,
                background: 'rgba(220, 38, 38, 0.12)',
                border: '1px solid rgba(220, 38, 38, 0.45)',
                borderRadius: 10,
                fontSize: 13, color: '#fecaca', lineHeight: 1.4,
              }}
            >
              <Circle
                className="h-3.5 w-3.5"
                style={{ marginTop: 2, fill: '#dc2626', color: '#dc2626', flexShrink: 0 }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: '#fca5a5', marginBottom: 4 }}>
                  This meeting will be recorded
                </div>
                <label
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8,
                    cursor: 'pointer', fontSize: 12,
                    color: 'rgba(252,165,165,0.85)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={recordingConsent}
                    onChange={(e) => setRecordingConsent(e.target.checked)}
                    style={{ marginTop: 2, accentColor: '#dc2626' }}
                    disabled={stage === 'waiting'}
                  />
                  <span>
                    I consent to my audio &amp; video being captured and stored.
                  </span>
                </label>
              </div>
            </div>
          )}

          {stage === 'knock' && (
            <form onSubmit={handleKnock} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Your name
                </label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Email <span className="text-gray-500 font-normal">(optional)</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@example.com"
                  className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {knockError && (
                <p className="text-xs text-red-400 mt-2">{knockError}</p>
              )}
              <button
                type="submit"
                disabled={
                  knockBusy ||
                  !name.trim() ||
                  Boolean(meeting?.record_meeting && !recordingConsent)
                }
                style={{
                  background: (
                    knockBusy ||
                    !name.trim() ||
                    Boolean(meeting?.record_meeting && !recordingConsent)
                  ) ? 'rgba(99,102,241,0.35)' : brandColor,
                }}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 rounded-lg transition"
              >
                {knockBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Ask to join
              </button>
            </form>
          )}

          {stage === 'waiting' && (
            <div className="text-center py-4">
              <Loader2 className="h-7 w-7 animate-spin text-indigo-400 mx-auto mb-2" />
              <p className="text-sm font-medium text-white mb-1">
                Waiting for {meeting?.host_name || 'the host'} to admit you…
              </p>
              <p className="text-xs text-gray-400">
                You'll join automatically once admitted.
              </p>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500 text-center mt-4">
          Powered by {orgName}
        </p>
      </div>
    </div>
  )
}

function GuestForceEnableMediaOnConnect() {
  const room = useRoomContext()
  const triedRef = useRef(0)
  useEffect(() => {
    if (!room) return
    const tryEnable = async () => {
      const lp = room.localParticipant
      if (!lp) return
      try {
        if (!lp.isMicrophoneEnabled) await lp.setMicrophoneEnabled(true)
        if (!lp.isCameraEnabled) await lp.setCameraEnabled(true)
      } catch (e: any) {
        // Device permission can be denied or the track can already be live;
        // neither should block the join. The guest can still enable manually
        // from the toolbar.
        console.warn('[mt] GuestForceEnable failed', { name: e?.name, message: e?.message })
      }
    }
    const onConnected = () => {
      triedRef.current += 1
      void tryEnable()
    }
    if (room.state === 'connected') {
      triedRef.current += 1
      void tryEnable()
    }
    room.on(RoomEvent.Connected, onConnected)
    const retry = setTimeout(() => void tryEnable(), 1500)
    return () => {
      room.off(RoomEvent.Connected, onConnected)
      clearTimeout(retry)
    }
  }, [room])
  return null
}

function GuestStage() {
  const tracks = useTracks(
    [
      { source: Track.Source.Camera, withPlaceholder: true },
      { source: Track.Source.ScreenShare, withPlaceholder: false },
    ],
    { onlySubscribed: false },
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <GridLayout tracks={tracks} style={{ height: '100%' }}>
          <ParticipantTile />
        </GridLayout>
      </div>
      <RoomAudioRenderer />
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: '0.5rem', padding: '0.5rem', background: '#1f2937',
      }}>
        <ControlBar
          variation="minimal"
          controls={{ microphone: true, camera: true, screenShare: true, leave: true, chat: true }}
        />
      </div>
    </div>
  )
}
