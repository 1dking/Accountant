import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Circle, Square, Loader2, Upload, PhoneOff } from 'lucide-react'
import {
  LiveKitRoom,
  GridLayout,
  ParticipantTile,
  RoomAudioRenderer,
  ControlBar,
  useTracks,
  useRoomContext,
} from '@livekit/components-react'
import '@livekit/components-styles'
import { Track } from 'livekit-client'
import { startMeeting, joinMeeting, endMeeting, uploadRecording } from '@/api/meetings'

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

function MeetingStage({ meetingId, onEndMeeting, endingMeeting }: {
  meetingId: string
  onEndMeeting: () => void
  endingMeeting: boolean
}) {
  const tracks = useTracks(
    [
      { source: Track.Source.Camera, withPlaceholder: true },
      { source: Track.Source.ScreenShare, withPlaceholder: false },
    ],
    { onlySubscribed: false },
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Video grid */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <GridLayout tracks={tracks} style={{ height: '100%' }}>
          <ParticipantTile />
        </GridLayout>
      </div>

      <RoomAudioRenderer />

      {/* LiveKit built-in controls + our extras */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.5rem', background: '#1f2937' }}>
        <ControlBar
          variation="minimal"
          controls={{
            microphone: true,
            camera: true,
            screenShare: true,
            leave: false,
            chat: true,
          }}
        />
        <RecordingControls meetingId={meetingId} />
        <button
          onClick={onEndMeeting}
          disabled={endingMeeting}
          className="lk-button lk-disconnect-button"
          style={{ background: '#dc2626', color: 'white', borderRadius: '9999px', padding: '0.5rem 1rem' }}
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
  const [error, setError] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(true)

  const action = searchParams.get('action') || 'start'

  useEffect(() => {
    if (!id) return
    setConnecting(true)
    const connect = action === 'join' ? joinMeeting(id) : startMeeting(id)
    connect
      .then((res) => {
        setToken(res.data.token)
        setRoomName(res.data.room_name)
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

  return (
    <div style={{ height: '100vh', background: '#111827' }}>
      <LiveKitRoom
        serverUrl={LIVEKIT_URL}
        token={token}
        connect={true}
        onDisconnected={handleDisconnect}
        data-lk-theme="default"
        style={{ height: '100%' }}
      >
        <MeetingStage
          meetingId={id!}
          onEndMeeting={handleEndMeeting}
          endingMeeting={endMut.isPending}
        />
      </LiveKitRoom>
    </div>
  )
}
