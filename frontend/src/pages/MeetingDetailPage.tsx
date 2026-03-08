import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Video, Phone, PhoneOff, Users, Calendar, Clock,
  Copy, Play, Download, Circle, Square, Loader2, Plus, X, Trash2,
  Lightbulb, CheckCircle2, AlertTriangle, TrendingUp, MessageSquare,
  Target, ChevronDown, ChevronRight,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  getMeeting, cancelMeeting, endMeeting, addParticipant,
  removeParticipant, getRecordingStreamUrl, deleteRecording,
} from '@/api/meetings'
import { coachApi } from '@/api/coach'
import type { MeetingStatus, MeetingParticipant } from '@/types/models'

function StatusBadge({ status }: { status: MeetingStatus }) {
  const config: Record<MeetingStatus, { bg: string; text: string; label: string; pulse?: boolean }> = {
    scheduled: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Scheduled' },
    in_progress: { bg: 'bg-green-100', text: 'text-green-700', label: 'In Progress', pulse: true },
    completed: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Completed' },
    cancelled: { bg: 'bg-red-100', text: 'text-red-700', label: 'Cancelled' },
  }
  const c = config[status]
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${c.bg} ${c.text}`}>
      {c.pulse && <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />}
      {c.label}
    </span>
  )
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
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

/* ── Meeting Intelligence Section ──────────────────────────────────────── */

function MeetingIntelligenceSection({ meetingId }: { meetingId: string }) {
  const queryClient = useQueryClient()
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true, action_items: true, topics: false, decisions: false,
    sentiment: false, talk_ratio: false, deal_signals: false,
    risk_flags: false, follow_ups: false, suggestions: false,
  })

  const { data: intelData, isLoading: intelLoading } = useQuery<any>({
    queryKey: ['meeting-intelligence', meetingId],
    queryFn: () => coachApi.getMeetingIntelligence(meetingId),
    enabled: !!meetingId,
  })

  const analyzeMut = useMutation({
    mutationFn: () => coachApi.analyzeMeeting(meetingId),
    onSuccess: () => {
      toast.success('Meeting analyzed successfully')
      queryClient.invalidateQueries({ queryKey: ['meeting-intelligence', meetingId] })
    },
    onError: (err: any) => toast.error(err?.message || 'Analysis failed'),
  })

  const toggleActionMut = useMutation({
    mutationFn: ({ intelId, index, completed }: { intelId: string; index: number; completed: boolean }) =>
      coachApi.toggleActionItem(intelId, index, completed),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['meeting-intelligence', meetingId] }),
  })

  const intel = intelData?.data
  const toggle = (key: string) => setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))

  if (intelLoading) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-amber-200 dark:border-amber-800 p-5 mt-6">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="h-5 w-5 text-amber-500" />
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Meeting Intelligence</h2>
        </div>
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
        </div>
      </div>
    )
  }

  if (!intel) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-amber-200 dark:border-amber-800 p-5 mt-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-amber-500" />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Meeting Intelligence</h2>
          </div>
          <button
            onClick={() => analyzeMut.mutate()}
            disabled={analyzeMut.isPending}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            {analyzeMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Lightbulb className="h-3.5 w-3.5" />}
            {analyzeMut.isPending ? 'Analyzing...' : 'Analyze with O-Brain'}
          </button>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
          No intelligence available yet. Click "Analyze" to extract insights from the meeting transcript.
        </p>
      </div>
    )
  }

  const SectionHeader = ({ label, sectionKey, icon: Icon, count }: { label: string; sectionKey: string; icon: any; count?: number }) => (
    <button
      onClick={() => toggle(sectionKey)}
      className="w-full flex items-center justify-between py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
    >
      <span className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-amber-500" />
        {label}
        {count !== undefined && <span className="text-xs text-gray-400">({count})</span>}
      </span>
      {expandedSections[sectionKey] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
    </button>
  )

  const completedItems: number[] = intel.action_items_completed || []

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-amber-200 dark:border-amber-800 p-5 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="h-5 w-5 text-amber-500" />
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Meeting Intelligence</h2>
        <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 rounded font-medium">O-Brain Coach</span>
      </div>

      {/* Summary */}
      {intel.summary_text && (
        <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-100 dark:border-amber-800">
          <p className="text-sm text-gray-800 dark:text-gray-200">{intel.summary_text}</p>
        </div>
      )}

      {/* Action Items */}
      {intel.action_items?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Action Items" sectionKey="action_items" icon={CheckCircle2} count={intel.action_items.length} />
          {expandedSections.action_items && (
            <div className="space-y-1.5 pb-3">
              {intel.action_items.map((item: any, idx: number) => (
                <div key={idx} className="flex items-start gap-2 py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800">
                  <button
                    onClick={() => toggleActionMut.mutate({ intelId: intel.id, index: idx, completed: !completedItems.includes(idx) })}
                    className={`mt-0.5 h-4 w-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                      completedItems.includes(idx)
                        ? 'bg-green-500 border-green-500 text-white'
                        : 'border-gray-300 dark:border-gray-600'
                    }`}
                  >
                    {completedItems.includes(idx) && <CheckCircle2 className="h-3 w-3" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${completedItems.includes(idx) ? 'line-through text-gray-400' : 'text-gray-800 dark:text-gray-200'}`}>
                      {item.task}
                    </p>
                    <div className="flex gap-2 text-xs text-gray-500 dark:text-gray-400">
                      {item.owner && <span>Owner: {item.owner}</span>}
                      {item.deadline && <span>Due: {item.deadline}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Topics */}
      {intel.topics?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Topics Discussed" sectionKey="topics" icon={MessageSquare} count={intel.topics.length} />
          {expandedSections.topics && (
            <div className="flex flex-wrap gap-1.5 pb-3">
              {intel.topics.map((topic: string, idx: number) => (
                <span key={idx} className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-full">{topic}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Decisions */}
      {intel.decisions?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Decisions Made" sectionKey="decisions" icon={Target} count={intel.decisions.length} />
          {expandedSections.decisions && (
            <ul className="space-y-1 pb-3 pl-4">
              {intel.decisions.map((d: string, idx: number) => (
                <li key={idx} className="text-sm text-gray-700 dark:text-gray-300 list-disc">{d}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Talk Ratio */}
      {intel.talk_ratio?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Talk Ratio" sectionKey="talk_ratio" icon={Users} />
          {expandedSections.talk_ratio && (
            <div className="space-y-2 pb-3">
              {intel.talk_ratio.map((p: any, idx: number) => (
                <div key={idx} className="flex items-center gap-3">
                  <span className="text-xs text-gray-600 dark:text-gray-400 w-24 truncate">{p.name}</span>
                  <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-2.5">
                    <div className="bg-amber-500 rounded-full h-2.5" style={{ width: `${p.percentage}%` }} />
                  </div>
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400 w-10 text-right">{p.percentage}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Deal Signals */}
      {intel.deal_signals?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Deal Signals" sectionKey="deal_signals" icon={TrendingUp} count={intel.deal_signals.length} />
          {expandedSections.deal_signals && (
            <div className="space-y-2 pb-3">
              {intel.deal_signals.map((sig: any, idx: number) => (
                <div key={idx} className={`p-2 rounded-lg text-sm ${sig.positive ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300' : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300'}`}>
                  <span className="font-medium capitalize">{sig.type?.replace(/_/g, ' ')}: </span>
                  <span className="italic">"{sig.text}"</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Risk Flags */}
      {intel.risk_flags?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Risk Flags" sectionKey="risk_flags" icon={AlertTriangle} count={intel.risk_flags.length} />
          {expandedSections.risk_flags && (
            <div className="space-y-1.5 pb-3">
              {intel.risk_flags.map((flag: any, idx: number) => (
                <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20">
                  <AlertTriangle className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                    flag.severity === 'high' ? 'text-red-600' : flag.severity === 'medium' ? 'text-yellow-600' : 'text-gray-500'
                  }`} />
                  <div>
                    <p className="text-sm text-gray-800 dark:text-gray-200">{flag.flag}</p>
                    <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${
                      flag.severity === 'high' ? 'bg-red-100 text-red-700' : flag.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                    }`}>{flag.severity}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Follow-ups */}
      {intel.follow_ups?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Suggested Follow-ups" sectionKey="follow_ups" icon={Calendar} count={intel.follow_ups.length} />
          {expandedSections.follow_ups && (
            <div className="space-y-1.5 pb-3">
              {intel.follow_ups.map((f: any, idx: number) => (
                <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium mt-0.5 ${
                    f.priority === 'high' ? 'bg-red-100 text-red-700' : f.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                  }`}>{f.priority}</span>
                  <div>
                    <p className="text-sm text-gray-800 dark:text-gray-200">{f.action}</p>
                    {f.suggested_date && <p className="text-xs text-gray-500">Suggested: {f.suggested_date}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Coach Suggestions */}
      {intel.suggestions?.length > 0 && (
        <div className="border-t border-gray-100 dark:border-gray-800">
          <SectionHeader label="Coach Suggestions" sectionKey="suggestions" icon={Lightbulb} count={intel.suggestions.length} />
          {expandedSections.suggestions && (
            <div className="space-y-1.5 pb-3">
              {intel.suggestions.map((s: string, idx: number) => (
                <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20">
                  <Lightbulb className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-gray-800 dark:text-gray-200">{s}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Main Page ─────────────────────────────────────────────────────────── */

export default function MeetingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [showAddParticipant, setShowAddParticipant] = useState(false)
  const [newParticipantEmail, setNewParticipantEmail] = useState('')
  const [playingRecordingId, setPlayingRecordingId] = useState<string | null>(null)
  const [copiedToken, setCopiedToken] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['meeting', id],
    queryFn: () => getMeeting(id!),
    enabled: !!id,
  })

  const cancelMut = useMutation({
    mutationFn: () => cancelMeeting(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
    },
  })

  const endMut = useMutation({
    mutationFn: () => endMeeting(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
    },
  })

  const addParticipantMut = useMutation({
    mutationFn: (email: string) => addParticipant(id!, { guest_email: email }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
      setNewParticipantEmail('')
      setShowAddParticipant(false)
    },
  })

  const removeParticipantMut = useMutation({
    mutationFn: (pid: string) => removeParticipant(id!, pid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
    },
  })

  const deleteRecordingMut = useMutation({
    mutationFn: (recordingId: string) => deleteRecording(recordingId),
    onSuccess: () => {
      toast.success('Recording deleted')
      queryClient.invalidateQueries({ queryKey: ['meeting', id] })
      queryClient.invalidateQueries({ queryKey: ['recordings'] })
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to delete recording')
    },
  })

  const meeting = data?.data

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400 dark:text-gray-500" />
      </div>
    )
  }

  if (!meeting) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500 dark:text-gray-400">Meeting not found</p>
        <button onClick={() => navigate('/meetings')} className="text-blue-600 dark:text-blue-400 hover:underline mt-2 text-sm">
          Back to Meetings
        </button>
      </div>
    )
  }

  const copyGuestLink = (participant: MeetingParticipant) => {
    if (!participant.join_token) return
    const url = `${window.location.origin}/meetings/${meeting.id}/guest?token=${participant.join_token}`
    navigator.clipboard.writeText(url)
    setCopiedToken(participant.id)
    setTimeout(() => setCopiedToken(null), 2000)
  }

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/meetings')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{meeting.title}</h1>
            <StatusBadge status={meeting.status} />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 mb-6">
        {meeting.status === 'scheduled' && (
          <>
            <button
              onClick={() => navigate(`/meetings/${meeting.id}/room`)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Video className="h-4 w-4" />
              Start Meeting
            </button>
            <button
              onClick={() => { if (confirm('Cancel this meeting?')) cancelMut.mutate() }}
              disabled={cancelMut.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
            >
              <PhoneOff className="h-4 w-4" />
              Cancel Meeting
            </button>
          </>
        )}
        {meeting.status === 'in_progress' && (
          <>
            <button
              onClick={() => navigate(`/meetings/${meeting.id}/room?action=join`)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
            >
              <Phone className="h-4 w-4" />
              Join Meeting
            </button>
            <button
              onClick={() => { if (confirm('End this meeting?')) endMut.mutate() }}
              disabled={endMut.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
            >
              <PhoneOff className="h-4 w-4" />
              End Meeting
            </button>
          </>
        )}
      </div>

      {/* Meeting Info */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 mb-6">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Meeting Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Scheduled Start</p>
            <p className="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500" />
              {formatDateTime(meeting.scheduled_start)}
            </p>
          </div>
          {meeting.scheduled_end && (
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Scheduled End</p>
              <p className="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500" />
                {formatDateTime(meeting.scheduled_end)}
              </p>
            </div>
          )}
          {meeting.actual_start && (
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Actual Start</p>
              <p className="text-sm text-gray-900 dark:text-gray-100">{formatDateTime(meeting.actual_start)}</p>
            </div>
          )}
          {meeting.actual_end && (
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Actual End</p>
              <p className="text-sm text-gray-900 dark:text-gray-100">{formatDateTime(meeting.actual_end)}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Recording</p>
            <p className="text-sm text-gray-900 dark:text-gray-100">{meeting.record_meeting ? 'Enabled' : 'Disabled'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Room</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 font-mono text-xs">{meeting.livekit_room_name}</p>
          </div>
        </div>
        {meeting.description && (
          <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Description</p>
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{meeting.description}</p>
          </div>
        )}
      </div>

      {/* Participants */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Users className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            Participants ({meeting.participants.length})
          </h2>
          {(meeting.status === 'scheduled' || meeting.status === 'in_progress') && (
            <button
              onClick={() => setShowAddParticipant(!showAddParticipant)}
              className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 font-medium"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Participant
            </button>
          )}
        </div>

        {showAddParticipant && (
          <div className="flex gap-2 mb-4">
            <input
              type="email"
              value={newParticipantEmail}
              onChange={(e) => setNewParticipantEmail(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addParticipantMut.mutate(newParticipantEmail) } }}
              placeholder="participant@example.com"
              className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            />
            <button
              onClick={() => addParticipantMut.mutate(newParticipantEmail)}
              disabled={!newParticipantEmail.trim() || addParticipantMut.isPending}
              className="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {addParticipantMut.isPending ? 'Adding...' : 'Add'}
            </button>
          </div>
        )}

        {meeting.participants.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No participants yet</p>
        ) : (
          <div className="space-y-2">
            {meeting.participants.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-950">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {p.guest_name || p.guest_email || p.user_id || 'Unknown'}
                    </p>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                      p.role === 'host' ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                    }`}>
                      {p.role}
                    </span>
                  </div>
                  {p.guest_email && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">{p.guest_email}</p>
                  )}
                  {p.joined_at && (
                    <p className="text-xs text-gray-400 dark:text-gray-500">Joined {formatDateTime(p.joined_at)}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {p.join_token && (
                    <button
                      onClick={() => copyGuestLink(p)}
                      className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700"
                      title="Copy guest invite link"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      {copiedToken === p.id ? 'Copied!' : 'Invite Link'}
                    </button>
                  )}
                  {p.role !== 'host' && (meeting.status === 'scheduled' || meeting.status === 'in_progress') && (
                    <button
                      onClick={() => removeParticipantMut.mutate(p.id)}
                      className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-500"
                      title="Remove participant"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recordings */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
          <Circle className="h-4 w-4 text-red-400" />
          Recordings ({meeting.recordings.length})
        </h2>

        {meeting.recordings.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No recordings</p>
        ) : (
          <div className="space-y-3">
            {meeting.recordings.map((rec) => (
              <div key={rec.id}>
                <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-950">
                  <div className="flex items-center gap-3">
                    <RecordingStatusBadge status={rec.status} />
                    <div>
                      <p className="text-sm text-gray-900 dark:text-gray-100">{formatDateTime(rec.created_at)}</p>
                      <div className="flex gap-3 text-xs text-gray-500 dark:text-gray-400">
                        {rec.duration_seconds != null && (
                          <span>{formatDuration(rec.duration_seconds)}</span>
                        )}
                        {rec.file_size != null && (
                          <span>{formatFileSize(rec.file_size)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {rec.status === 'available' && (
                      <>
                        <button
                          onClick={() => setPlayingRecordingId(playingRecordingId === rec.id ? null : rec.id)}
                          className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 font-medium"
                        >
                          {playingRecordingId === rec.id ? (
                            <><Square className="h-3.5 w-3.5" /> Stop</>
                          ) : (
                            <><Play className="h-3.5 w-3.5" /> Play</>
                          )}
                        </button>
                        <a
                          href={getRecordingStreamUrl(rec.id)}
                          download
                          className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 font-medium"
                        >
                          <Download className="h-3.5 w-3.5" />
                          Download
                        </a>
                      </>
                    )}
                    <button
                      onClick={() => { if (confirm('Delete this recording?')) deleteRecordingMut.mutate(rec.id) }}
                      disabled={deleteRecordingMut.isPending}
                      className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700 font-medium"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  </div>
                </div>

                {/* Inline video player */}
                {playingRecordingId === rec.id && rec.status === 'available' && (
                  <div className="mt-2 rounded-lg overflow-hidden bg-black">
                    <video
                      src={getRecordingStreamUrl(rec.id)}
                      controls
                      autoPlay
                      className="w-full max-h-96"
                    >
                      Your browser does not support the video element.
                    </video>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Meeting Intelligence (O-Brain Coach) */}
      {(meeting.status === 'completed' || meeting.status === 'in_progress') && (
        <MeetingIntelligenceSection meetingId={meeting.id} />
      )}
    </div>
  )
}
