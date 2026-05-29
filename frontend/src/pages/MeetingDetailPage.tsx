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
  getCalendarUrls, sendMeetingInvites, getMeetingTranscript,
  getMeetingSummary, getMeetingQuoteDraft, reviewMeetingQuoteDraft,
  getMeetingPriorContext,
} from '@/api/meetings'
import { coachApi } from '@/api/coach'
import type { MeetingStatus, MeetingParticipant } from '@/types/models'

/** Commit 17 — cross-meeting context.
 *
 * Shows the last meeting with the same contact + recent action items
 * + recent topics. Hidden when the meeting has no contact_id. Great
 * for accountants reviewing a client meeting — surfaces "last time
 * we spoke, you committed to X" without opening the prior meeting. */
function PriorContextSection({ meetingId }: { meetingId: string }) {
  const q = useQuery({
    queryKey: ['meeting-prior-context', meetingId],
    queryFn: async () => (await getMeetingPriorContext(meetingId)).data,
    retry: false,
  })
  if (q.isError || q.isLoading || !q.data) return null
  const ctx = q.data
  // Empty payload = no contact_id; hide entirely.
  if (!ctx.contact_id) return null
  const hasLast = ctx.last_meeting != null
  const hasActions = (ctx.recent_action_items?.length ?? 0) > 0
  const hasTopics = (ctx.recent_topics?.length ?? 0) > 0
  if (!hasLast && !hasActions && !hasTopics) return null

  function fmtDate(s: string | null | undefined): string {
    if (!s) return ''
    return new Date(s).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    })
  }

  return (
    <div className="mb-6 p-4 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl">
      <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" /> Prior context
      </p>

      {hasLast && ctx.last_meeting && (
        <div className="mb-3">
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
            Last meeting · {fmtDate(ctx.last_meeting.actual_end || ctx.last_meeting.scheduled_start)}
          </p>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
            {ctx.last_meeting.title}
          </p>
          {ctx.last_meeting.summary_text && (
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
              {ctx.last_meeting.summary_text}
            </p>
          )}
        </div>
      )}

      {hasActions && (
        <div className="mb-3">
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
            Open action items from previous meetings
          </p>
          <ul className="space-y-1">
            {ctx.recent_action_items!.map((ai, i) => (
              <li key={i} className="text-sm text-gray-800 dark:text-gray-200 flex items-start gap-2">
                <span className="text-slate-400 mt-1">•</span>
                <span className="flex-1">{ai.description || ai.title}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasTopics && (
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
            Recent topics
          </p>
          <ul className="space-y-1">
            {ctx.recent_topics!.map((t, i) => (
              <li key={i} className="text-sm text-gray-800 dark:text-gray-200">
                <span className="font-medium">{t.topic}</span>
                {t.decision && (
                  <span className="text-gray-600 dark:text-gray-400"> — {t.decision}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}


/** Commit 15 — AI quote/invoice draft.
 *
 * Surfaces ONLY when Claude detected scope + pricing in the transcript.
 * Renders the draft with an explicit review gate — the host must click
 * "I've reviewed this" before the data flows anywhere external. NEVER
 * auto-sends. Hidden entirely when status is SKIPPED or 404. */
function QuoteDraftSection({ meetingId }: { meetingId: string }) {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['meeting-quote-draft', meetingId],
    queryFn: async () => (await getMeetingQuoteDraft(meetingId)).data,
    refetchInterval: (query) => {
      const d = query.state.data as any
      if (!d) return 12000
      if (d.status === 'pending' || d.status === 'processing') return 12000
      return false
    },
    retry: false,
  })
  const reviewMut = useMutation({
    mutationFn: () => reviewMeetingQuoteDraft(meetingId),
    onSuccess: () => {
      toast.success('Marked as reviewed')
      qc.invalidateQueries({ queryKey: ['meeting-quote-draft', meetingId] })
    },
    onError: (e: any) => toast.error(`Review failed: ${e?.message || 'unknown'}`),
  })

  if (q.isError) return null
  if (q.isLoading) return null
  const d = q.data
  if (!d) return null
  // SKIPPED / FAILED states aren't worth showing inline — Claude
  // determined there's no quote here.
  if (d.status === 'skipped' || d.status === 'failed') return null

  const confidenceColor = d.confidence === 'high'
    ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-950 border-emerald-300 dark:border-emerald-800'
    : d.confidence === 'medium'
    ? 'text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-950 border-amber-300 dark:border-amber-800'
    : 'text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600'

  return (
    <div className="mb-6 p-4 bg-gradient-to-br from-amber-50 to-rose-50 dark:from-amber-950/40 dark:to-rose-950/40 border border-amber-200 dark:border-amber-800 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider">
          AI quote draft
        </p>
        {d.status !== 'available' && d.status !== 'reviewed' && (
          <span className="inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300">
            <Loader2 className="h-3 w-3 animate-spin" />
            Drafting…
          </span>
        )}
        {d.confidence && (d.status === 'available' || d.status === 'reviewed') && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border uppercase tracking-wider ${confidenceColor}`}>
            {d.confidence} confidence
          </span>
        )}
      </div>

      {(d.status === 'pending' || d.status === 'processing') && (
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Claude is checking whether the meeting discussed scope + pricing…
        </p>
      )}

      {(d.status === 'available' || d.status === 'reviewed') && (
        <>
          {d.draft_title && (
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">
              {d.draft_title}
            </h3>
          )}
          {d.draft_summary && (
            <p className="text-sm text-gray-700 dark:text-gray-300 mb-3">
              {d.draft_summary}
            </p>
          )}
          {d.line_items.length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden mb-3">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-3 py-2">Description</th>
                    <th className="text-right px-3 py-2 w-16">Qty</th>
                    <th className="text-right px-3 py-2 w-20">Unit</th>
                    <th className="text-right px-3 py-2 w-20">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {d.line_items.map((li, i) => (
                    <tr key={i} className="border-t border-gray-100 dark:border-gray-800">
                      <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{li.description}</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{li.quantity}</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                        {(d.currency || 'USD')} {li.unit_price.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100">
                        {(d.currency || 'USD')} {li.total.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50 dark:bg-gray-800 border-t-2 border-gray-200 dark:border-gray-700">
                  <tr>
                    <td colSpan={3} className="px-3 py-2 text-right text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider">Estimated total</td>
                    <td className="px-3 py-2 text-right text-base font-bold text-gray-900 dark:text-gray-100">
                      {(d.currency || 'USD')} {(d.estimated_total ?? 0).toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
          {d.notes && (
            <p className="text-xs text-gray-600 dark:text-gray-400 italic mb-3">
              {d.notes}
            </p>
          )}
          <div className="flex items-center justify-between gap-3 pt-2 border-t border-amber-200 dark:border-amber-800">
            <p className="text-xs text-amber-800 dark:text-amber-200 leading-snug">
              <strong>Review before sending.</strong> AI-generated drafts may misread numbers.
              Verify every line item against the transcript.
            </p>
            {d.status === 'reviewed' ? (
              <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="h-4 w-4" /> Reviewed
              </span>
            ) : (
              <button
                onClick={() => reviewMut.mutate()}
                disabled={reviewMut.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50 rounded-lg whitespace-nowrap transition-colors"
              >
                {reviewMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                I've reviewed this
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}


/** Commit 12 — AI summary section.
 *
 * Renders the Claude-generated summary, key topics + decisions, action
 * items, and next steps. Polls every 10 sec while pending/processing;
 * stops once available/failed. Hidden when 404 (no transcript yet, so
 * nothing to summarize). */
function SummarySection({ meetingId }: { meetingId: string }) {
  const q = useQuery({
    queryKey: ['meeting-summary', meetingId],
    queryFn: async () => (await getMeetingSummary(meetingId)).data,
    refetchInterval: (query) => {
      const d = query.state.data as any
      if (!d) return 10000
      if (d.status === 'available' || d.status === 'failed') return false
      return 10000
    },
    retry: false,
  })

  if (q.isError) return null
  if (q.isLoading) return null
  const s = q.data
  if (!s) return null

  return (
    <div className="mb-6 p-4 bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-950/40 dark:to-violet-950/40 border border-indigo-200 dark:border-indigo-800 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">
          AI summary
        </p>
        {s.status !== 'available' && s.status !== 'failed' && (
          <span className="inline-flex items-center gap-1.5 text-xs text-indigo-700 dark:text-indigo-300">
            <Loader2 className="h-3 w-3 animate-spin" />
            Generating…
          </span>
        )}
      </div>

      {s.status === 'failed' && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Summary failed{s.error_message ? `: ${s.error_message}` : ''}.
        </p>
      )}

      {s.status === 'available' && (
        <>
          {s.summary_text && (
            <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed mb-4">
              {s.summary_text}
            </p>
          )}

          {s.action_items.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" /> Action items ({s.action_items.length})
              </h4>
              <ul className="space-y-1.5">
                {s.action_items.map((ai, i) => (
                  <li key={i} className="text-sm text-gray-800 dark:text-gray-200 flex items-start gap-2">
                    <span className="text-indigo-500 mt-1">•</span>
                    <span className="flex-1">
                      {ai.text}
                      {(ai.assignee || ai.due_hint) && (
                        <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                          {ai.assignee && <span>· {ai.assignee}</span>}
                          {ai.due_hint && <span> · {ai.due_hint}</span>}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {s.topics.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5" /> Topics
              </h4>
              <ul className="space-y-1.5">
                {s.topics.map((t, i) => (
                  <li key={i} className="text-sm text-gray-800 dark:text-gray-200">
                    <span className="font-medium">{t.topic}</span>
                    {t.decision && (
                      <span className="text-gray-600 dark:text-gray-400"> — {t.decision}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {s.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Target className="h-3.5 w-3.5" /> Next steps
              </h4>
              <ul className="space-y-1.5">
                {s.next_steps.map((ns, i) => (
                  <li key={i} className="text-sm text-gray-800 dark:text-gray-200 flex items-start gap-2">
                    <span className="text-indigo-500 mt-1">→</span>
                    <span>{ns}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!s.summary_text && s.topics.length === 0 && s.action_items.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No spoken content to summarize.
            </p>
          )}
        </>
      )}

      {(s.status === 'pending' || s.status === 'processing') && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Reading the transcript and pulling out the key points…
        </p>
      )}
    </div>
  )
}


/** Commit 11 — Transcript section.
 *
 * Polls /meetings/{id}/transcript every 8 sec while the row is still
 * PROCESSING. Renders speaker-labeled segments once AVAILABLE; falls
 * back to a friendly "transcript is being generated" while pending.
 * Hides itself entirely when the meeting has no recording yet (404).
 */
function TranscriptSection({ meetingId }: { meetingId: string }) {
  const q = useQuery({
    queryKey: ['meeting-transcript', meetingId],
    queryFn: async () => (await getMeetingTranscript(meetingId)).data,
    // Poll only while still processing; stop once available/failed.
    refetchInterval: (query) => {
      const d = query.state.data as any
      if (!d) return 8000
      if (d.status === 'available' || d.status === 'failed') return false
      return 8000
    },
    retry: false,
  })

  // 404 = no transcript yet (no recording). Hide the section.
  if (q.isError) return null
  if (q.isLoading) return null

  const t = q.data
  if (!t) return null

  return (
    <div className="mb-6 p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Transcript
        </p>
        {t.status !== 'available' && t.status !== 'failed' && (
          <span className="inline-flex items-center gap-1.5 text-xs text-cyan-700 dark:text-cyan-300">
            <Loader2 className="h-3 w-3 animate-spin" />
            {t.status === 'pending' ? 'Queued…' : 'Transcribing…'}
          </span>
        )}
        {t.status === 'available' && t.segments.length > 0 && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {t.language ? `${t.language.toUpperCase()} · ` : ''}
            {t.segments.length} segments
          </span>
        )}
      </div>

      {t.status === 'failed' && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Transcription failed{t.error_message ? `: ${t.error_message}` : ''}.
        </p>
      )}

      {t.status === 'available' && t.segments.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No spoken audio detected in this recording.
        </p>
      )}

      {t.status === 'available' && t.segments.length > 0 && (
        <div className="max-h-96 overflow-y-auto space-y-3 pr-2">
          {t.segments.map((seg, i) => (
            <div key={i} className="flex gap-3">
              <div className="flex-shrink-0 w-16 text-xs text-gray-400 dark:text-gray-500 font-mono tabular-nums pt-0.5">
                {fmtTime(seg.start)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 mb-0.5">
                  Speaker {seg.speaker}
                </div>
                <div className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                  {seg.text}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {(t.status === 'pending' || t.status === 'processing') && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          This usually takes ~2-3 minutes after the meeting ends.
        </p>
      )}
    </div>
  )
}

function fmtTime(seconds: number): string {
  const s = Math.floor(seconds)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}


/** Commit 9 — Calendar invite section.
 *
 * Three add-to-calendar buttons (Google / Outlook / .ics download)
 * + a "Re-send invites" button that hits the email-send endpoint
 * and surfaces a toast with the sent / failed counts.
 */
function CalendarInviteSection({ meetingId }: { meetingId: string }) {
  const urlsQ = useQuery({
    queryKey: ['meeting-calendar-urls', meetingId],
    queryFn: async () => (await getCalendarUrls(meetingId)).data,
  })
  const sendMut = useMutation({
    mutationFn: () => sendMeetingInvites(meetingId),
    onSuccess: (res) => {
      const r = res.data
      if (r.failed === 0 && r.sent > 0) {
        toast.success(`Invites sent (${r.sent})`)
      } else if (r.sent === 0 && r.failed === 0) {
        toast('No invitees to send to')
      } else if (r.failed > 0 && r.sent > 0) {
        toast(`${r.sent} sent · ${r.failed} failed`)
      } else {
        toast.error(`Could not send: ${r.errors[0] || 'unknown error'}`)
      }
    },
    onError: (e: any) => toast.error(`Send failed: ${e?.message || 'unknown'}`),
  })

  if (urlsQ.isLoading || !urlsQ.data) return null
  const u = urlsQ.data

  return (
    <div className="mb-6 p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        Calendar invite
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <a
          href={u.google}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg transition-colors"
        >
          <Calendar className="h-3.5 w-3.5" /> Add to Google Calendar
        </a>
        <a
          href={u.outlook}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg transition-colors"
        >
          <Calendar className="h-3.5 w-3.5" /> Add to Outlook
        </a>
        <a
          href={u.ics_url}
          download="meeting.ics"
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg transition-colors"
        >
          <Download className="h-3.5 w-3.5" /> Download .ics
        </a>
        <button
          onClick={() => sendMut.mutate()}
          disabled={sendMut.isPending}
          className="ml-auto inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950 hover:bg-indigo-100 dark:hover:bg-indigo-900 border border-indigo-200 dark:border-indigo-800 rounded-lg disabled:opacity-50 transition-colors"
        >
          {sendMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Re-send invites
        </button>
      </div>
    </div>
  )
}


/** Commit 8 — shareable meeting URL display + copy button.
 *
 * Renders right under the meeting title on MeetingDetailPage. The URL
 * is the public guest-join page (/m/:slug); recipients enter name +
 * email matching their invite, then knock the lobby. */
function ShareLinkRow({ slug }: { slug: string }) {
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/m/${slug}`

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      toast.success('Meeting link copied')
      setTimeout(() => setCopied(false), 1800)
    } catch {
      toast.error('Could not copy link')
    }
  }

  return (
    <div className="flex items-center gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400">
      <span className="font-medium">Share link:</span>
      <code className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded font-mono text-[11px] text-gray-700 dark:text-gray-300 truncate max-w-md">
        {url}
      </code>
      <button
        onClick={handleCopy}
        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950 rounded transition-colors"
        title="Copy to clipboard"
      >
        <Copy className="h-3.5 w-3.5" />
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  )
}


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
          {/* Commit 8 — shareable meeting URL. Guest visits this URL
              and goes through the email-match + knock flow. */}
          {meeting.slug && meeting.status !== 'cancelled' && (
            <ShareLinkRow slug={meeting.slug} />
          )}
        </div>
      </div>

      {/* Commit 17 — prior-context "last time we spoke" panel.
          Renders only when the meeting has a contact_id AND there's
          actually prior data to show. */}
      <PriorContextSection meetingId={meeting.id} />

      {/* Commit 9 — Calendar invite buttons (Google / Outlook / .ics)
          + re-send. Renders for any meeting that hasn't been cancelled
          or completed (no point re-sending invites after the fact). */}
      {meeting.status !== 'cancelled' && meeting.status !== 'completed' && (
        <CalendarInviteSection meetingId={meeting.id} />
      )}

      {/* Commit 15 — AI quote/invoice draft when Claude detected
          scope + pricing. Highest-liability: explicit review gate. */}
      <QuoteDraftSection meetingId={meeting.id} />

      {/* Commit 12 — Claude-generated summary + action items + next
          steps. Renders above the raw transcript so the user sees
          the high-value AI synthesis first. */}
      <SummarySection meetingId={meeting.id} />

      {/* Commit 11 — AI transcript (auto-generated when the meeting
          recording finishes; hidden until a recording exists). */}
      <TranscriptSection meetingId={meeting.id} />

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
          {meeting.scheduled_start && (
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Scheduled Start</p>
              <p className="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500" />
                {formatDateTime(meeting.scheduled_start)}
              </p>
            </div>
          )}
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
