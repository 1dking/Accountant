import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PhoneOff, Circle, Square, Loader2, Upload } from 'lucide-react'
import { LiveKitRoom, VideoConference, useRoomContext } from '@livekit/components-react'
import '@livekit/components-styles'
import { startMeeting, joinMeeting, endMeeting, uploadRecording } from '@/api/meetings'

// In dev: set VITE_LIVEKIT_URL=ws://localhost:7880 in .env
// In production: auto-derives wss://domain/api/meetings/livekit-proxy
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
      // Collect all audio and video tracks from the room
      const tracks: MediaStreamTrack[] = []

      for (const p of room.remoteParticipants.values()) {
        for (const pub of p.trackPublications.values()) {
          if (pub.track?.mediaStreamTrack) {
            tracks.push(pub.track.mediaStreamTrack)
          }
        }
      }

      // Add local tracks
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

      recorder.start(1000) // collect chunks every second
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

  // Stop recording if component unmounts
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  return (
    <>
      {!isRecording ? (
        <button
          onClick={handleStartRecording}
          disabled={isUploading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors disabled:opacity-50"
          title="Start recording"
        >
          <Circle className="h-4 w-4 text-red-400" />
          Record
        </button>
      ) : (
        <button
          onClick={handleStopRecording}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors animate-pulse"
          title="Stop recording"
        >
          <Square className="h-4 w-4" />
          Stop Recording
        </button>
      )}

      {isUploading && (
        <span className="flex items-center gap-1.5 text-xs text-blue-400">
          <Upload className="h-3.5 w-3.5 animate-bounce" />
          {uploadProgress}
        </span>
      )}

      {!isUploading && uploadProgress && (
        <span className="text-xs text-green-400">{uploadProgress}</span>
      )}
    </>
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

  const handleHangUp = () => {
    if (confirm('End this meeting for all participants?')) {
      endMut.mutate()
    } else {
      navigate(`/meetings/${id}`)
    }
  }

  if (connecting) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-white mx-auto mb-4" />
          <p className="text-white text-sm">Connecting to meeting...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
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
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <p className="text-gray-400 dark:text-gray-500 text-sm">Unable to join meeting</p>
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-900 flex flex-col">
      {/* Video Area */}
      <div className="flex-1 relative">
        <LiveKitRoom
          serverUrl={LIVEKIT_URL}
          token={token}
          connect={true}
          onDisconnected={handleDisconnect}
          data-lk-theme="default"
          style={{ height: '100%' }}
        >
          <VideoConference />

          {/* Control Bar */}
          <div className="absolute bottom-0 left-0 right-0 bg-gray-800/90 backdrop-blur border-t border-gray-700 px-4 py-3">
            <div className="flex items-center justify-center gap-3">
              <RecordingControls meetingId={id!} />

              {/* Hang up */}
              <button
                onClick={handleHangUp}
                disabled={endMut.isPending}
                className="flex items-center gap-2 px-6 py-2 text-sm font-medium text-white bg-red-600 rounded-full hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                <PhoneOff className="h-4 w-4" />
                {endMut.isPending ? 'Ending...' : 'Hang Up'}
              </button>
            </div>
          </div>
        </LiveKitRoom>
      </div>
    </div>
  )
}
