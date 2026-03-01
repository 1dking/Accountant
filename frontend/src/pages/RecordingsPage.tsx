import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Video, Search, Play, Download, Clock, Calendar, Loader2, Square, Trash2 } from 'lucide-react'
import { listRecordings, listRecordingsByContact, getRecordingStreamUrl, deleteRecording } from '@/api/meetings'
import type { MeetingRecording } from '@/types/models'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}h ${m % 60}m`
  }
  return `${m}m ${s}s`
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function RecordingStatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string }> = {
    recording: { bg: 'bg-red-100', text: 'text-red-700' },
    processing: { bg: 'bg-yellow-100', text: 'text-yellow-700' },
    available: { bg: 'bg-green-100', text: 'text-green-700' },
    failed: { bg: 'bg-red-100', text: 'text-red-700' },
  }
  const c = config[status] || config.failed
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.bg} ${c.text}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

export default function RecordingsPage() {
  const queryClient = useQueryClient()
  const [selectedContact, setSelectedContact] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [playingId, setPlayingId] = useState<string | null>(null)

  const deleteRecordingMut = useMutation({
    mutationFn: (recordingId: string) => deleteRecording(recordingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recordings'] })
      queryClient.invalidateQueries({ queryKey: ['recordings-by-contact'] })
    },
  })

  const { data: allRecordingsData, isLoading: loadingAll } = useQuery({
    queryKey: ['recordings'],
    queryFn: () => listRecordings(),
  })

  const { data: byContactData, isLoading: loadingByContact } = useQuery({
    queryKey: ['recordings-by-contact'],
    queryFn: () => listRecordingsByContact(),
  })

  const allRecordings: MeetingRecording[] = allRecordingsData?.data ?? []
  const contactGroups = byContactData?.data ?? []

  // Build contact sidebar items
  const contactItems = useMemo(() => {
    return contactGroups.map((g) => ({
      id: g.contact_id,
      name: g.contact_name || 'Unknown Contact',
      count: g.recordings.length,
    }))
  }, [contactGroups])

  // Get filtered recordings
  const filteredRecordings = useMemo(() => {
    let recs: MeetingRecording[]

    if (selectedContact === null) {
      recs = allRecordings
    } else {
      const group = contactGroups.find((g) => g.contact_id === selectedContact)
      recs = group?.recordings ?? []
    }

    // Apply search filter
    if (search) {
      const q = search.toLowerCase()
      recs = recs.filter(
        (r) => r.meeting_id.toLowerCase().includes(q) || r.mime_type.toLowerCase().includes(q)
      )
    }

    // Apply date filter
    if (dateFilter) {
      recs = recs.filter((r) => r.created_at.startsWith(dateFilter))
    }

    return recs
  }, [allRecordings, contactGroups, selectedContact, search, dateFilter])

  const isLoading = loadingAll || loadingByContact

  return (
    <div className="p-6 h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Recordings</h1>
      </div>

      <div className="flex gap-6 h-[calc(100vh-10rem)]">
        {/* Left sidebar: contacts */}
        <div className="w-64 flex-shrink-0 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-100 dark:border-gray-700">
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Contacts</h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            <button
              onClick={() => setSelectedContact(null)}
              className={`w-full text-left px-4 py-2.5 text-sm border-b border-gray-50 transition-colors ${
                selectedContact === null
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span>All Recordings</span>
                <span className="text-xs text-gray-400 dark:text-gray-500">{allRecordings.length}</span>
              </div>
            </button>
            {contactItems.map((item) => (
              <button
                key={item.id || 'none'}
                onClick={() => setSelectedContact(item.id)}
                className={`w-full text-left px-4 py-2.5 text-sm border-b border-gray-50 transition-colors ${
                  selectedContact === item.id
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="truncate">{item.name}</span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">{item.count}</span>
                </div>
              </button>
            ))}
            {!loadingByContact && contactItems.length === 0 && (
              <p className="px-4 py-6 text-xs text-gray-400 dark:text-gray-500 text-center">No contacts with recordings</p>
            )}
          </div>
        </div>

        {/* Main area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Filters */}
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search recordings..."
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {dateFilter && (
              <button
                onClick={() => setDateFilter('')}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700"
              >
                Clear date
              </button>
            )}
          </div>

          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400 dark:text-gray-500" />
            </div>
          )}

          {/* Empty state */}
          {!isLoading && filteredRecordings.length === 0 && (
            <div className="text-center py-20">
              <Video className="h-10 w-10 mx-auto mb-3 text-gray-300" />
              <p className="text-gray-500 dark:text-gray-400 text-sm">No recordings found</p>
              <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">Recording will appear here after a meeting is recorded</p>
            </div>
          )}

          {/* Recordings grid */}
          {!isLoading && filteredRecordings.length > 0 && (
            <div className="flex-1 overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredRecordings.map((rec) => (
                  <div key={rec.id} className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
                    {/* Video player or thumbnail area */}
                    {playingId === rec.id && rec.status === 'available' ? (
                      <div className="bg-black">
                        <video
                          src={getRecordingStreamUrl(rec.id)}
                          controls
                          autoPlay
                          className="w-full aspect-video"
                        >
                          Your browser does not support the video element.
                        </video>
                      </div>
                    ) : (
                      <div className="bg-gray-900 aspect-video flex items-center justify-center relative">
                        <Video className="h-8 w-8 text-gray-600 dark:text-gray-400" />
                        {rec.status === 'available' && (
                          <button
                            onClick={() => setPlayingId(rec.id)}
                            className="absolute inset-0 flex items-center justify-center group"
                          >
                            <div className="h-12 w-12 bg-white/20 backdrop-blur rounded-full flex items-center justify-center group-hover:bg-white/30 transition-colors">
                              <Play className="h-5 w-5 text-white ml-0.5" />
                            </div>
                          </button>
                        )}
                      </div>
                    )}

                    {/* Card info */}
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <RecordingStatusBadge status={rec.status} />
                        {playingId === rec.id && (
                          <button
                            onClick={() => setPlayingId(null)}
                            className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 flex items-center gap-1"
                          >
                            <Square className="h-3 w-3" /> Close
                          </button>
                        )}
                      </div>

                      <div className="space-y-1.5 text-xs text-gray-500 dark:text-gray-400">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="h-3 w-3" />
                          <span>{formatDate(rec.created_at)}</span>
                        </div>
                        {rec.duration_seconds != null && (
                          <div className="flex items-center gap-1.5">
                            <Clock className="h-3 w-3" />
                            <span>{formatDuration(rec.duration_seconds)}</span>
                          </div>
                        )}
                        {rec.file_size != null && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">{formatFileSize(rec.file_size)}</p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2 mt-3 pt-3 border-t border-gray-50">
                        {rec.status === 'available' && (
                          <>
                            <button
                              onClick={() => setPlayingId(playingId === rec.id ? null : rec.id)}
                              className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 font-medium"
                            >
                              <Play className="h-3.5 w-3.5" />
                              {playingId === rec.id ? 'Playing' : 'Play'}
                            </button>
                            <a
                              href={getRecordingStreamUrl(rec.id)}
                              download
                              className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 font-medium"
                            >
                              <Download className="h-3.5 w-3.5" />
                              Download
                            </a>
                          </>
                        )}
                        <button
                          onClick={() => { if (confirm('Delete this recording?')) deleteRecordingMut.mutate(rec.id) }}
                          disabled={deleteRecordingMut.isPending}
                          className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700 font-medium ml-auto"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
