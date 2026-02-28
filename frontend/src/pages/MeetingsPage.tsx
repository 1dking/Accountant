import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Video, Plus, Users, Calendar, Clock, Loader2 } from 'lucide-react'
import { listMeetings, type MeetingFilters } from '@/api/meetings'
import type { MeetingListItem, MeetingStatus } from '@/types/models'

const STATUS_TABS: { value: string; label: string }[] = [
  { value: 'scheduled', label: 'Upcoming' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Past' },
  { value: 'cancelled', label: 'Cancelled' },
]

function StatusBadge({ status }: { status: MeetingStatus }) {
  const config: Record<MeetingStatus, { bg: string; text: string; label: string; pulse?: boolean }> = {
    scheduled: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Scheduled' },
    in_progress: { bg: 'bg-green-100', text: 'text-green-700', label: 'In Progress', pulse: true },
    completed: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Completed' },
    cancelled: { bg: 'bg-red-100', text: 'text-red-700', label: 'Cancelled' },
  }
  const c = config[status]
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${c.bg} ${c.text}`}>
      {c.pulse && <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />}
      {c.label}
    </span>
  )
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

export default function MeetingsPage() {
  const navigate = useNavigate()
  const [statusTab, setStatusTab] = useState('scheduled')
  const [filters, setFilters] = useState<MeetingFilters>({ page: 1, page_size: 25 })

  const { data, isLoading } = useQuery({
    queryKey: ['meetings', { ...filters, status: statusTab }],
    queryFn: () => listMeetings({ ...filters, status: statusTab }),
  })

  const meetings: MeetingListItem[] = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Meetings</h1>
        <button
          onClick={() => navigate('/meetings/new')}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Schedule Meeting
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6 w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => { setStatusTab(tab.value); setFilters(f => ({ ...f, page: 1 })) }}
            className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors ${
              statusTab === tab.value
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && meetings.length === 0 && (
        <div className="text-center py-20">
          <Video className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500 text-sm">No meetings found</p>
          <p className="text-gray-400 text-xs mt-1">
            {statusTab === 'scheduled'
              ? 'Schedule a meeting to get started'
              : `No ${statusTab.replace('_', ' ')} meetings`}
          </p>
        </div>
      )}

      {/* Meeting cards */}
      {!isLoading && meetings.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {meetings.map((meeting) => (
            <div
              key={meeting.id}
              onClick={() => navigate(`/meetings/${meeting.id}`)}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md hover:border-gray-200 cursor-pointer transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900 line-clamp-1">{meeting.title}</h3>
                <StatusBadge status={meeting.status} />
              </div>

              <div className="space-y-2 text-xs text-gray-500">
                <div className="flex items-center gap-2">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>{formatDateTime(meeting.scheduled_start)}</span>
                </div>
                {meeting.scheduled_end && (
                  <div className="flex items-center gap-2">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Ends {formatTime(meeting.scheduled_end)}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Users className="h-3.5 w-3.5" />
                  <span>{meeting.participant_count} participant{meeting.participant_count !== 1 ? 's' : ''}</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-4 pt-3 border-t border-gray-50">
                {meeting.status === 'in_progress' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/meetings/${meeting.id}/room`) }}
                    className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
                  >
                    <Video className="h-3.5 w-3.5" />
                    Join Meeting
                  </button>
                )}
                {meeting.status === 'scheduled' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/meetings/${meeting.id}/room`) }}
                    className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <Video className="h-3.5 w-3.5" />
                    Start Meeting
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-gray-500">
            Page {meta.page} of {meta.total_pages} ({meta.total_count} meetings)
          </p>
          <div className="flex gap-2">
            <button
              disabled={meta.page <= 1}
              onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) - 1 }))}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              disabled={meta.page >= meta.total_pages}
              onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) + 1 }))}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
