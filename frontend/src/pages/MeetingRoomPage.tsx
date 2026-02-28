import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PhoneOff, Circle, Square, Loader2 } from 'lucide-react'
import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import '@livekit/components-styles'
import { startMeeting, joinMeeting, endMeeting, startRecording, stopRecording } from '@/api/meetings'

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || 'ws://localhost:7880'

export default function MeetingRoomPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const [token, setToken] = useState<string | null>(null)
  const [roomName, setRoomName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isRecording, setIsRecording] = useState(false)
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

  const startRecordingMut = useMutation({
    mutationFn: () => startRecording(id!),
    onSuccess: () => setIsRecording(true),
  })

  const stopRecordingMut = useMutation({
    mutationFn: () => stopRecording(id!),
    onSuccess: () => setIsRecording(false),
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
        <p className="text-gray-400 text-sm">Unable to join meeting</p>
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
        </LiveKitRoom>
      </div>

      {/* Control Bar */}
      <div className="bg-gray-800 border-t border-gray-700 px-4 py-3">
        <div className="flex items-center justify-center gap-3">
          {/* Recording controls */}
          {!isRecording ? (
            <button
              onClick={() => startRecordingMut.mutate()}
              disabled={startRecordingMut.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors disabled:opacity-50"
              title="Start recording"
            >
              <Circle className="h-4 w-4 text-red-400" />
              {startRecordingMut.isPending ? 'Starting...' : 'Record'}
            </button>
          ) : (
            <button
              onClick={() => stopRecordingMut.mutate()}
              disabled={stopRecordingMut.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              title="Stop recording"
            >
              <Square className="h-4 w-4" />
              {stopRecordingMut.isPending ? 'Stopping...' : 'Stop Recording'}
            </button>
          )}

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
    </div>
  )
}
