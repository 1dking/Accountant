import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import {
  Circle, Square, Loader2, Upload, PhoneOff,
  UserPlus, UserMinus, Bell,
  Mic, MicOff, Video as VideoIcon, VideoOff, ScreenShare,
  Copy, Check, Link as LinkIcon,
} from 'lucide-react'
import {
  LiveKitRoom,
  GridLayout,
  ParticipantTile,
  RoomAudioRenderer,
  useTracks,
  useRoomContext,
  useLocalParticipant,
} from '@livekit/components-react'
import '@livekit/components-styles'
import { Track, RoomEvent } from 'livekit-client'
import {
  startMeeting, joinMeeting, endMeeting, uploadRecording,
  listLobby, admitFromLobby, denyFromLobby, admitAllFromLobby,
} from '@/api/meetings'
import PreJoinGate from '@/components/meetings/PreJoinGate'
import { useBranding } from '@/hooks/useBranding'
import type { LocalUserChoices } from '@livekit/components-react'

const LIVEKIT_URL =
  import.meta.env.VITE_LIVEKIT_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/meetings/livekit-proxy`

function RecordingControls({ meetingId }: { meetingId: string }) {
  const room = useRoomContext()
  const queryClient = useQueryClient()
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const [isRecording, setIsRecording] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState('')

  const handleStartRecording = useCallback(async () => {
    try {
      const tracks: MediaStreamTrack[] = []

      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (pub.track?.mediaStreamTrack) {
            tracks.push(pub.track.mediaStreamTrack)
          }
        }
      }

      const localP = room.localParticipant
      for (const pub of localP.trackPublications.values()) {
        if (pub.track?.mediaStreamTrack) {
          tracks.push(pub.track.mediaStreamTrack)
        }
      }

      if (tracks.length === 0) {
        alert('No media tracks available to record.')
        return
      }

      const stream = new MediaStream(tracks)
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
        ? 'video/webm;codecs=vp9,opus'
        : MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
          ? 'video/webm;codecs=vp8,opus'
          : 'video/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      recorder.onstop = async () => {
        if (chunksRef.current.length === 0) return
        const blob = new Blob(chunksRef.current, { type: mimeType })
        chunksRef.current = []

        setIsUploading(true)
        setUploadProgress('Uploading recording...')
        try {
          await uploadRecording(meetingId, blob)
          setUploadProgress('Recording saved!')
          queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
          queryClient.invalidateQueries({ queryKey: ['recordings'] })
          setTimeout(() => setUploadProgress(''), 3000)
        } catch (err: any) {
          setUploadProgress(`Upload failed: ${err?.message || 'Unknown error'}`)
          setTimeout(() => setUploadProgress(''), 5000)
        } finally {
          setIsUploading(false)
        }
      }

      recorder.start(1000)
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch (err: any) {
      alert(`Failed to start recording: ${err?.message || 'Unknown error'}`)
    }
  }, [room, meetingId, queryClient])

  const handleStopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
      setIsRecording(false)
    }
  }, [])

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  return (
    <div className="lk-button-group" style={{ display: 'flex', gap: '0.5rem' }}>
      {!isRecording ? (
        <button
          onClick={handleStartRecording}
          disabled={isUploading}
          className="lk-button"
          title="Start recording"
        >
          <Circle className="h-4 w-4 text-red-400" />
          Record
        </button>
      ) : (
        <button
          onClick={handleStopRecording}
          className="lk-button"
          title="Stop recording"
          style={{ background: '#dc2626' }}
        >
          <Square className="h-4 w-4" />
          Stop
        </button>
      )}

      {isUploading && (
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#60a5fa' }}>
          <Upload className="h-3.5 w-3.5" />
          {uploadProgress}
        </span>
      )}
      {!isUploading && uploadProgress && (
        <span style={{ fontSize: '12px', color: '#4ade80' }}>{uploadProgress}</span>
      )}
    </div>
  )
}

/** Belt-and-suspenders: after the room connects, explicitly enable
 *  mic + camera on the local participant. Even if LK or some
 *  intermediate state has them muted, this forces a getUserMedia +
 *  publish. Retries once after 1 second in case the room wasn't
 *  fully connected on the first pass.
 *
 *  Background: removing PostConnectMuteSync should've left tracks
 *  on, but the user kept reporting muted tracks + the silhouette
 *  placeholder. This component forces the state we want regardless
 *  of what other code path may have ended up muting them.
 */
function ForceEnableMediaOnConnect() {
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
      } catch (e) {
        console.error('[meeting] ForceEnable failed', e)
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
    // Safety retry — sometimes the first call fires before the SFU
    // is ready to accept publishes.
    const retry = setTimeout(() => void tryEnable(), 1500)
    return () => {
      room.off(RoomEvent.Connected, onConnected)
      clearTimeout(retry)
    }
  }, [room])
  return null
}

/** Commit 19.3 — switched from useTrackToggle to useLocalParticipant
 *  + explicit setMicrophoneEnabled / setCameraEnabled. The hook
 *  abstraction wasn't engaging actual track publication for users
 *  who joined with audio={false}/video={false} via PreJoin. The
 *  direct API guarantees a real getUserMedia + publish on click.
 *
 *  useLocalParticipant's isMicrophoneEnabled / isCameraEnabled are
 *  reactive — they re-render on track-publish / track-unpublish /
 *  mute / unmute events fired by the LiveKit room.
 */
function MicToggleButton() {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant()
  const [pending, setPending] = useState(false)
  const onClick = async () => {
    if (!localParticipant || pending) return
    setPending(true)
    try {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)
    } catch (e) {
      console.error('[meeting] mic toggle failed', e)
    } finally {
      setPending(false)
    }
  }
  return (
    <button
      onClick={onClick}
      disabled={pending}
      style={mrpToggleStyle(isMicrophoneEnabled)}
      title={isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'}
      aria-label={isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'}
    >
      {isMicrophoneEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
    </button>
  )
}

function CamToggleButton() {
  const { localParticipant, isCameraEnabled } = useLocalParticipant()
  const [pending, setPending] = useState(false)
  const onClick = async () => {
    if (!localParticipant || pending) return
    setPending(true)
    try {
      await localParticipant.setCameraEnabled(!isCameraEnabled)
    } catch (e) {
      console.error('[meeting] camera toggle failed', e)
    } finally {
      setPending(false)
    }
  }
  return (
    <button
      onClick={onClick}
      disabled={pending}
      style={mrpToggleStyle(isCameraEnabled)}
      title={isCameraEnabled ? 'Stop camera' : 'Start camera'}
      aria-label={isCameraEnabled ? 'Stop camera' : 'Start camera'}
    >
      {isCameraEnabled ? <VideoIcon className="h-4 w-4" /> : <VideoOff className="h-4 w-4" />}
    </button>
  )
}

function ScreenShareToggleButton() {
  const { localParticipant, isScreenShareEnabled } = useLocalParticipant()
  const [pending, setPending] = useState(false)
  const onClick = async () => {
    if (!localParticipant || pending) return
    setPending(true)
    try {
      await localParticipant.setScreenShareEnabled(!isScreenShareEnabled)
    } catch (e) {
      console.error('[meeting] screen share toggle failed', e)
    } finally {
      setPending(false)
    }
  }
  return (
    <button
      onClick={onClick}
      disabled={pending}
      style={mrpToggleStyle(isScreenShareEnabled, !isScreenShareEnabled)}
      title={isScreenShareEnabled ? 'Stop sharing' : 'Share screen'}
      aria-label={isScreenShareEnabled ? 'Stop sharing' : 'Share screen'}
    >
      <ScreenShare className="h-4 w-4" />
    </button>
  )
}


function mrpToggleStyle(enabled: boolean, neutral = false): React.CSSProperties {
  if (neutral) {
    return {
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 40, height: 40, borderRadius: '9999px',
      background: 'rgba(255, 255, 255, 0.10)', color: 'white',
      border: '1px solid rgba(255, 255, 255, 0.18)',
      cursor: 'pointer',
    }
  }
  return {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    width: 40, height: 40, borderRadius: '9999px',
    background: enabled ? 'rgba(99, 102, 241, 0.35)' : 'rgba(239, 68, 68, 0.30)',
    color: 'white',
    border: enabled
      ? '1px solid rgba(99, 102, 241, 0.65)'
      : '1px solid rgba(239, 68, 68, 0.55)',
    cursor: 'pointer',
  }
}


function ServerRecordingIndicator() {
  // Commit 7 — when meeting.record_meeting=true, the backend started
  // a LiveKit Egress on start_meeting. The client doesn't need to do
  // anything; this indicator just tells the user recording is on.
  return (
    <span
      title="Server-side recording is active for this meeting"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 12px',
        background: 'rgba(220, 38, 38, 0.18)',
        border: '1px solid rgba(220, 38, 38, 0.45)',
        borderRadius: '999px',
        color: '#fecaca',
        fontSize: '12px',
        fontWeight: 500,
      }}
    >
      <span
        style={{
          width: 8, height: 8, borderRadius: '50%',
          background: '#dc2626',
          boxShadow: '0 0 0 0 rgba(220, 38, 38, 0.6)',
          animation: 'mrp-rec-pulse 1.6s ease-in-out infinite',
        }}
      />
      Recording
      {/* Keyframes injected inline so we don't need a global CSS file
          change for one-off pulse animation. */}
      <style>{`@keyframes mrp-rec-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.55); }
        50% { box-shadow: 0 0 0 5px rgba(220, 38, 38, 0); }
      }`}</style>
    </span>
  )
}

/** Commit 8 — Host-side lobby panel.
 *
 * Polls /lobby every 3 sec while at least one guest is waiting (and
 * every 8 sec otherwise to catch fresh knocks). Renders waiting
 * guests with Admit / Deny buttons.
 *
 * Pulses on the panel border when someone is newly waiting so the host
 * notices even if their attention is on the video stage. */
function LobbyPanel({ meetingId }: { meetingId: string }) {
  const qc = useQueryClient()
  const [hasWaiting, setHasWaiting] = useState(false)

  const lobbyQ = useQuery({
    queryKey: ['meeting-lobby', meetingId],
    queryFn: async () => (await listLobby(meetingId)).data || [],
    refetchInterval: hasWaiting ? 3000 : 8000,
  })

  useEffect(() => {
    setHasWaiting((lobbyQ.data?.length ?? 0) > 0)
  }, [lobbyQ.data])

  const admitMut = useMutation({
    mutationFn: (lobbyId: string) => admitFromLobby(meetingId, lobbyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meeting-lobby', meetingId] }),
  })
  const denyMut = useMutation({
    mutationFn: (lobbyId: string) => denyFromLobby(meetingId, lobbyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meeting-lobby', meetingId] }),
  })
  // Commit 19 — Admit-all for large meetings. Fires the per-row admit
  // in sequence; LiveKit handles each token issuance independently.
  const admitAllMut = useMutation({
    mutationFn: (ids: string[]) => admitAllFromLobby(meetingId, ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meeting-lobby', meetingId] }),
  })

  const waiting = lobbyQ.data ?? []
  if (waiting.length === 0) return null

  return (
    <div style={{
      position: 'absolute', top: 12, left: 12, zIndex: 10,
      minWidth: 280, maxWidth: 360,
      background: 'rgba(15, 18, 32, 0.94)',
      backdropFilter: 'blur(20px) saturate(180%)',
      WebkitBackdropFilter: 'blur(20px) saturate(180%)',
      border: '1px solid rgba(99, 102, 241, 0.45)',
      borderRadius: 12,
      boxShadow: '0 16px 40px rgba(0, 0, 0, 0.5)',
      padding: 12,
      color: 'white',
      animation: 'mrp-lobby-pulse 2s ease-in-out infinite',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 8, marginBottom: 8,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
          textTransform: 'uppercase', color: 'rgba(199, 210, 254, 0.9)',
        }}>
          <Bell className="h-3.5 w-3.5" />
          Waiting · {waiting.length}
        </div>
        {/* Commit 19 — Admit-all CTA only when 2+ are waiting */}
        {waiting.length >= 2 && (
          <button
            onClick={() => admitAllMut.mutate(waiting.map((p: any) => p.id))}
            disabled={admitAllMut.isPending}
            title="Admit everyone waiting"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              padding: '3px 8px', fontSize: 10.5, fontWeight: 600,
              background: 'rgba(16, 185, 129, 0.22)',
              border: '1px solid rgba(16, 185, 129, 0.5)',
              borderRadius: 6, color: '#a7f3d0', cursor: 'pointer',
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}
          >
            <UserPlus className="h-3 w-3" /> Admit all
          </button>
        )}
      </div>
      {/* Commit 19 — scrollable list when many guests knock at once.
          ~6 entries (each ~52px) fit before the scroll kicks in. */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 6,
        maxHeight: 320, overflowY: 'auto',
      }}>
        {waiting.map((p: any) => (
          <div key={p.id} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 8, padding: '6px 8px',
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 8,
          }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'white', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {p.guest_name || 'Guest'}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.50)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {p.guest_email}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                onClick={() => admitMut.mutate(p.id)}
                disabled={admitMut.isPending}
                title="Admit"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 3,
                  padding: '5px 9px', fontSize: 11, fontWeight: 500,
                  background: 'rgba(16, 185, 129, 0.22)',
                  border: '1px solid rgba(16, 185, 129, 0.5)',
                  borderRadius: 6, color: '#a7f3d0', cursor: 'pointer',
                }}
              >
                <UserPlus className="h-3 w-3" /> Admit
              </button>
              <button
                onClick={() => denyMut.mutate(p.id)}
                disabled={denyMut.isPending}
                title="Deny"
                style={{
                  display: 'inline-flex', alignItems: 'center',
                  padding: '5px 7px', fontSize: 11,
                  background: 'rgba(239, 68, 68, 0.18)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  borderRadius: 6, color: '#fecaca', cursor: 'pointer',
                }}
              >
                <UserMinus className="h-3 w-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
      <style>{`@keyframes mrp-lobby-pulse {
        0%, 100% { box-shadow: 0 16px 40px rgba(0,0,0,0.5), 0 0 0 0 rgba(99,102,241,0.45); }
        50%      { box-shadow: 0 16px 40px rgba(0,0,0,0.5), 0 0 0 6px rgba(99,102,241,0); }
      }`}</style>
    </div>
  )
}


/** Host-facing share button. Opens a small popover showing the public
 *  /m/{slug} URL with a copy-to-clipboard CTA. Anyone with the link
 *  lands on MeetingJoinPage, knocks at the lobby (name only, email
 *  optional), and waits for the host to admit them. */
function ShareLinkButton({ slug }: { slug: string }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/m/${slug}`
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // Fallback for older browsers / lacking clipboard permission.
      const t = document.createElement('textarea')
      t.value = url
      document.body.appendChild(t)
      t.select()
      try { document.execCommand('copy') } catch { /* ignore */ }
      document.body.removeChild(t)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    }
  }
  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          background: '#374151', color: 'white', borderRadius: '9999px',
          padding: '0.5rem 0.95rem', border: 'none',
          display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
          fontSize: 13, fontWeight: 500, cursor: 'pointer',
        }}
        title="Share meeting link"
      >
        <LinkIcon className="h-4 w-4" />
        Share
      </button>
      {open && (
        <div
          style={{
            position: 'absolute', bottom: 'calc(100% + 8px)', left: '50%',
            transform: 'translateX(-50%)',
            background: '#1f2937', border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 12, padding: 14, width: 320,
            boxShadow: '0 12px 32px rgba(0,0,0,0.45)', zIndex: 30,
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 600, color: 'white', marginBottom: 6 }}>
            Anyone with this link can knock
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginBottom: 10 }}>
            They'll wait in the lobby until you admit them.
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              readOnly
              value={url}
              onClick={(e) => (e.target as HTMLInputElement).select()}
              style={{
                flex: 1, padding: '8px 10px', fontSize: 12,
                background: '#0f172a', color: 'white',
                border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
                outline: 'none',
              }}
            />
            <button
              onClick={copy}
              style={{
                padding: '8px 12px', fontSize: 12, fontWeight: 600,
                background: copied ? '#16a34a' : '#4f46e5',
                color: 'white', border: 'none', borderRadius: 8,
                cursor: 'pointer', display: 'inline-flex',
                alignItems: 'center', gap: 5,
              }}
              title={copied ? 'Copied!' : 'Copy link'}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function MeetingStage({ meetingId, slug, onEndMeeting, endingMeeting, recordMeeting }: {
  meetingId: string
  slug: string | null
  onEndMeeting: () => void
  endingMeeting: boolean
  recordMeeting: boolean
}) {
  const tracks = useTracks(
    [
      { source: Track.Source.Camera, withPlaceholder: true },
      { source: Track.Source.ScreenShare, withPlaceholder: false },
    ],
    { onlySubscribed: false },
  )
  const { logoUrl, orgName } = useBranding()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Video grid */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <GridLayout tracks={tracks} style={{ height: '100%' }}>
          <ParticipantTile />
        </GridLayout>
        {logoUrl && (
          <img
            src={logoUrl}
            alt={orgName}
            style={{
              position: 'absolute', top: 12, left: 12, zIndex: 10,
              height: 28, maxWidth: 140, objectFit: 'contain',
              opacity: 0.85, pointerEvents: 'none',
              filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))',
            }}
          />
        )}
        {/* Recording indicator — top-right corner of the stage when
            server-side Egress is recording (Commit 7). */}
        {recordMeeting && (
          <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10 }}>
            <ServerRecordingIndicator />
          </div>
        )}
        {/* Commit 8 — Host's lobby panel: shows waiting guests with
            Admit/Deny buttons. Polls every 3s when someone's waiting. */}
        <LobbyPanel meetingId={meetingId} />
      </div>

      <RoomAudioRenderer />

      {/* Commit 19.2 — Custom control bar using LiveKit's TrackToggle
          hook directly instead of <ControlBar>. ControlBar was rendering
          empty in some browser/permission combos (mic + cam buttons
          silently absent). Explicit toggles guarantee visible controls.
          When record_meeting=true the server handles recording via
          Egress, so we hide the client-side MediaRecorder controls. */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: '0.5rem', padding: '0.75rem', background: '#1f2937',
      }}>
        <MicToggleButton />
        <CamToggleButton />
        <ScreenShareToggleButton />
        {slug && <ShareLinkButton slug={slug} />}
        {!recordMeeting && <RecordingControls meetingId={meetingId} />}
        <button
          onClick={onEndMeeting}
          disabled={endingMeeting}
          style={{
            background: '#dc2626', color: 'white', borderRadius: '9999px',
            padding: '0.5rem 1rem', border: 'none',
            display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
            fontSize: 13, fontWeight: 500, cursor: 'pointer',
            opacity: endingMeeting ? 0.6 : 1,
          }}
        >
          <PhoneOff className="h-4 w-4" />
          {endingMeeting ? 'Ending...' : 'End Meeting'}
        </button>
      </div>
    </div>
  )
}

export default function MeetingRoomPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const [token, setToken] = useState<string | null>(null)
  const [roomName, setRoomName] = useState<string | null>(null)
  const [recordMeeting, setRecordMeeting] = useState(false)
  const [slug, setSlug] = useState<string | null>(null)
  // Title isn't returned by start/join token endpoints today; the
  // PreJoinGate handles undefined cleanly. Leave the state as a
  // forward-compat hook for when we add title to those responses.
  const [meetingTitle] = useState<string | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(true)
  // Commit 10 — user has passed the device-check + recording consent
  // gate. Until then, render PreJoinGate instead of LiveKitRoom.
  const [userChoices, setUserChoices] = useState<LocalUserChoices | null>(null)

  const action = searchParams.get('action') || 'start'

  useEffect(() => {
    if (!id) return
    setConnecting(true)

    const connectToMeeting = async () => {
      if (action === 'join') {
        return joinMeeting(id)
      }
      // When starting, try startMeeting first. If it fails (e.g. meeting is
      // already in progress and another user started it), fall back to join
      // so we don't recreate the room and kick existing participants.
      try {
        return await startMeeting(id)
      } catch {
        return joinMeeting(id)
      }
    }

    connectToMeeting()
      .then((res) => {
        setToken(res.data.token)
        setRoomName(res.data.room_name)
        setRecordMeeting(Boolean(res.data.record_meeting))
        setSlug(res.data.slug ?? null)
      })
      .catch((err) => {
        setError(err?.message || 'Failed to connect to meeting')
      })
      .finally(() => {
        setConnecting(false)
      })
  }, [id, action])

  const endMut = useMutation({
    mutationFn: () => endMeeting(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
      navigate(`/meetings/${id}`)
    },
  })

  const handleDisconnect = useCallback(() => {
    navigate(`/meetings/${id}`)
  }, [navigate, id])

  const handleEndMeeting = () => {
    if (confirm('End this meeting for all participants?')) {
      endMut.mutate()
    } else {
      navigate(`/meetings/${id}`)
    }
  }

  if (connecting) {
    return (
      <div className="h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-white mx-auto mb-4" />
          <p className="text-white text-sm">Connecting to meeting...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-4">{error}</p>
          <button
            onClick={() => navigate(`/meetings/${id}`)}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            Back to Meeting
          </button>
        </div>
      </div>
    )
  }

  if (!token || !roomName) {
    return (
      <div className="h-screen bg-gray-900 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Unable to join meeting</p>
      </div>
    )
  }

  // Commit 10 — show PreJoinGate until the user has previewed devices
  // (and, if record_meeting=true, explicitly consented). Then drop
  // into LiveKitRoom with their chosen camera/mic.
  if (!userChoices) {
    return (
      <PreJoinGate
        recordMeeting={recordMeeting}
        meetingTitle={meetingTitle}
        onJoin={setUserChoices}
      />
    )
  }

  return (
    <div style={{ height: '100vh', background: '#111827' }}>
      <LiveKitRoom
        serverUrl={LIVEKIT_URL}
        token={token}
        connect={true}
        onDisconnected={handleDisconnect}
        // Always publish mic + camera on connect — simplest possible
        // form so the LK SDK picks the OS default device deterministically.
        // Gating on userChoices.*Enabled previously meant LiveKitRoom
        // started with audio=false/video=false (no tracks), and the
        // in-room toggles' setMicrophoneEnabled(true) silently failed
        // when the PreJoin preview hadn't fully released the device
        // handle. Tracks are now always published; PostConnectMuteSync
        // re-mutes them after connect if the user wanted to start muted.
        audio={true}
        video={true}
        data-lk-theme="default"
        style={{ height: '100%' }}
      >
        <ForceEnableMediaOnConnect />
        <MeetingStage
          meetingId={id!}
          slug={slug}
          onEndMeeting={handleEndMeeting}
          endingMeeting={endMut.isPending}
          recordMeeting={recordMeeting}
        />
      </LiveKitRoom>
    </div>
  )
}
