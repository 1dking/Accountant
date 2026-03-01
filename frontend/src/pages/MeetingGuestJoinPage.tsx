import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { Video, Loader2 } from 'lucide-react'
import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import '@livekit/components-styles'
import { joinMeetingAsGuest } from '@/api/meetings'

const LIVEKIT_URL =
  import.meta.env.VITE_LIVEKIT_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/meetings/livekit-proxy`

export default function MeetingGuestJoinPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const guestToken = searchParams.get('token') || ''

  const [guestName, setGuestName] = useState('')
  const [lkToken, setLkToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [joining, setJoining] = useState(false)
  const [joined, setJoined] = useState(false)

  if (!guestToken) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-8 max-w-sm w-full text-center">
          <Video className="h-10 w-10 mx-auto mb-4 text-red-400" />
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-2">Invalid Invite Link</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            This meeting invite link is missing a required token. Please ask the host for a new link.
          </p>
        </div>
      </div>
    )
  }

  const handleJoin = async () => {
    if (!id || !guestName.trim()) return
    setJoining(true)
    setError(null)
    try {
      const res = await joinMeetingAsGuest(id, guestToken, guestName.trim())
      setLkToken(res.data.token)
      setJoined(true)
    } catch (err: any) {
      setError(err?.message || 'Failed to join meeting')
    } finally {
      setJoining(false)
    }
  }

  if (joined && lkToken) {
    return (
      <div className="h-screen bg-gray-900 flex flex-col">
        <LiveKitRoom
          serverUrl={LIVEKIT_URL}
          token={lkToken}
          connect={true}
          data-lk-theme="default"
          style={{ height: '100%' }}
        >
          <VideoConference />
        </LiveKitRoom>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-8 max-w-sm w-full">
        <div className="text-center mb-6">
          <Video className="h-10 w-10 mx-auto mb-3 text-blue-500" />
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">Join Meeting</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Enter your name to join as a guest</p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Your Name</label>
            <input
              type="text"
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleJoin() }}
              placeholder="Enter your name"
              autoFocus
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <button
            onClick={handleJoin}
            disabled={!guestName.trim() || joining}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {joining ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Joining...
              </>
            ) : (
              <>
                <Video className="h-4 w-4" />
                Join Meeting
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
