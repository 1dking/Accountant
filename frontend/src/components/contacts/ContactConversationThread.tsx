import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  AlertCircle, ArrowDownLeft, ArrowUpRight, Bot, Check, Mail, Pause,
  Phone, Send, Sparkles, Voicemail,
} from 'lucide-react'
import {
  listContactConversations,
  sendSms,
  type ConversationEvent,
} from '@/api/communication'
import { api } from '@/api/client'
import { wsClient } from '@/api/websocket'
import { useAuthStore } from '@/stores/authStore'

interface Props {
  contactId: string
  contactPhone: string | null | undefined
  contactEngineEnabled?: boolean | null
  contactEnginePausedUntil?: string | null
}

function pauseRelativeLabel(iso: string | null | undefined): string | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  const diffMs = t - Date.now()
  if (diffMs <= 0) return null
  const min = Math.floor(diffMs / 60000)
  if (min < 60) return `${min}m`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h`
  const day = Math.floor(hr / 24)
  return `${day}d`
}

function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diffMs = Date.now() - t
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  // Otherwise show date
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function StatusIcon({ status }: { status: string | null }) {
  if (!status) return null
  if (status === 'sent' || status === 'delivered') {
    return <Check className="h-3 w-3 text-blue-300" />
  }
  if (status === 'failed') {
    return <AlertCircle className="h-3 w-3 text-red-300" />
  }
  return null
}

export default function ContactConversationThread({
  contactId,
  contactPhone,
  contactEngineEnabled,
  contactEnginePausedUntil,
}: Props) {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [smsText, setSmsText] = useState('')
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [engineEnabled, setEngineEnabled] = useState<boolean | null>(
    contactEngineEnabled ?? null,
  )

  useEffect(() => {
    setEngineEnabled(contactEngineEnabled ?? null)
  }, [contactEngineEnabled])

  const engineDefault = !!user?.conversation_reply_enabled
  const effectiveEngineOn =
    engineEnabled === null ? engineDefault : engineEnabled

  const toggleEngineMut = useMutation({
    mutationFn: (newVal: boolean | null) =>
      api.put(`/contacts/${contactId}/conversation-engine`, { enabled: newVal }),
    onSuccess: (_resp, vars) => {
      setEngineEnabled(vars as boolean | null)
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] })
      const wasPaused = !!pauseRelativeLabel(contactEnginePausedUntil)
      if (vars === true && wasPaused) {
        toast.success('Pause cleared — AI will respond to next inbound')
      } else {
        toast.success(
          vars === true ? 'AI auto-reply: ON for this contact'
            : vars === false ? 'AI auto-reply: OFF for this contact'
              : 'AI auto-reply: using default',
        )
      }
    },
    onError: (e: any) => toast.error(`Toggle failed: ${e.message || ''}`),
  })
  const [isTabVisible, setIsTabVisible] = useState(
    typeof document !== 'undefined' ? document.visibilityState === 'visible' : true,
  )

  useEffect(() => {
    const onVis = () => setIsTabVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  // Live SMS push — refetch the thread when a matching contact_id event
  // arrives. WS is the fast path; polling remains as a 10s fallback so
  // we never miss a message if WS is wedged.
  useEffect(() => {
    const unsub = wsClient.on('sms.received', (ev) => {
      const eventContactId = (ev.data as any)?.contact_id
      if (eventContactId === contactId) {
        queryClient.invalidateQueries({
          queryKey: ['contact-conversations', contactId],
        })
      }
    })
    return () => {
      unsub()
    }
  }, [contactId, queryClient])

  const { data, isLoading } = useQuery({
    queryKey: ['contact-conversations', contactId],
    queryFn: () => listContactConversations(contactId),
    enabled: !!contactId,
    refetchInterval: isTabVisible ? 10_000 : false,
  })
  const events: ConversationEvent[] = (data?.data ?? []) as ConversationEvent[]

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events.length])

  const sendMut = useMutation({
    mutationFn: () =>
      sendSms({
        to_number: contactPhone!,
        body: smsText.trim(),
        contact_id: contactId,
      }),
    onSuccess: () => {
      setSmsText('')
      queryClient.invalidateQueries({ queryKey: ['contact-conversations', contactId] })
      queryClient.invalidateQueries({ queryKey: ['contact-activities', contactId] })
    },
    onError: (e: any) => toast.error(`Failed: ${e.message || 'SMS send failed'}`),
  })

  return (
    <div className="flex flex-col h-full min-h-[400px]">
      {/* AI auto-reply toggle bar — shows pause state when active */}
      {(() => {
        const pauseLabel = pauseRelativeLabel(contactEnginePausedUntil)
        const isPaused = !!pauseLabel
        return (
          <div className="flex items-center justify-between px-3 py-2 bg-indigo-50/50 dark:bg-indigo-900/10 border-b border-indigo-100 dark:border-indigo-900/30 text-xs">
            <span className="flex items-center gap-1.5 text-indigo-700 dark:text-indigo-300">
              <Bot className="h-3.5 w-3.5" />
              AI auto-reply:{' '}
              <span className={effectiveEngineOn ? 'font-semibold' : ''}>
                {effectiveEngineOn ? 'ON' : 'OFF'}
              </span>
              {engineEnabled === null && (
                <span className="text-indigo-400">(using default)</span>
              )}
              {isPaused && (
                <span className="flex items-center gap-1 ml-2 text-amber-600 dark:text-amber-400">
                  <Pause className="h-3 w-3" />
                  Paused for {pauseLabel}
                </span>
              )}
            </span>
            {isPaused ? (
              <button
                onClick={() => toggleEngineMut.mutate(true)}
                disabled={toggleEngineMut.isPending}
                className="px-2 py-0.5 rounded text-[11px] bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-50"
                title="Clear the manual-reply pause so AI responds to the next inbound"
              >
                {toggleEngineMut.isPending ? 'Resuming…' : 'Resume now'}
              </button>
            ) : (
              <div className="flex gap-1">
                <button
                  onClick={() => toggleEngineMut.mutate(true)}
                  disabled={toggleEngineMut.isPending}
                  className={`px-2 py-0.5 rounded text-[11px] ${
                    engineEnabled === true
                      ? 'bg-indigo-600 text-white'
                      : 'text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/30'
                  }`}
                >
                  On
                </button>
                <button
                  onClick={() => toggleEngineMut.mutate(false)}
                  disabled={toggleEngineMut.isPending}
                  className={`px-2 py-0.5 rounded text-[11px] ${
                    engineEnabled === false
                      ? 'bg-gray-600 text-white'
                      : 'text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/30'
                  }`}
                >
                  Off
                </button>
                <button
                  onClick={() => toggleEngineMut.mutate(null)}
                  disabled={toggleEngineMut.isPending}
                  className={`px-2 py-0.5 rounded text-[11px] ${
                    engineEnabled === null
                      ? 'bg-blue-500 text-white'
                      : 'text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/30'
                  }`}
                >
                  Default
                </button>
              </div>
            )}
          </div>
        )
      })()}

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-2 py-4 space-y-3"
        style={{ maxHeight: '60vh' }}
      >
        {isLoading ? (
          <div className="text-center text-sm text-gray-400 py-12">Loading…</div>
        ) : events.length === 0 ? (
          <div className="text-center text-sm text-gray-400 dark:text-gray-500 py-12">
            <Phone className="h-8 w-8 mx-auto mb-2 opacity-40" />
            No messages yet. Start the thread below.
          </div>
        ) : (
          events.map((ev) => {
            if (ev.type === 'email') {
              return <EmailEvent key={ev.id} ev={ev} />
            }
            if (ev.type === 'voicemail') {
              return (
                <div key={ev.id} className="flex flex-col items-start max-w-[80%]">
                  <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-3 w-full">
                    <div className="flex items-center gap-2 text-xs text-purple-700 dark:text-purple-300 mb-1">
                      <Voicemail className="h-3.5 w-3.5" />
                      <span className="font-medium">Voicemail</span>
                      {ev.recording_duration_seconds != null && (
                        <span className="text-purple-500">
                          · {ev.recording_duration_seconds}s
                        </span>
                      )}
                    </div>
                    {ev.recording_url_path && (
                      <audio
                        controls
                        controlsList="nodownload"
                        preload="metadata"
                        className="w-full h-8 mb-2"
                      >
                        <source
                          src={`${ev.recording_url_path}?token=${encodeURIComponent(
                            localStorage.getItem('access_token') ?? '',
                          )}`}
                          type="audio/mpeg"
                        />
                      </audio>
                    )}
                    {ev.body ? (
                      <div className="text-sm text-gray-800 dark:text-gray-200 italic">
                        "{ev.body}"
                      </div>
                    ) : ev.status === 'pending' ? (
                      <div className="text-xs text-gray-500 italic">Transcribing…</div>
                    ) : ev.status === 'failed' ? (
                      <div className="text-xs text-gray-400 italic">
                        Transcript unavailable
                      </div>
                    ) : null}
                  </div>
                  <span className="text-[10px] text-gray-400 mt-1 px-1">
                    {relativeTime(ev.timestamp)}
                  </span>
                </div>
              )
            }
            const isOut = ev.type === 'sms_out'
            return (
              <div
                key={ev.id}
                className={`flex flex-col ${isOut ? 'items-end' : 'items-start'} max-w-[80%] ${
                  isOut ? 'ml-auto' : ''
                }`}
              >
                <div
                  className={`rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
                    isOut
                      ? 'bg-blue-600 text-white rounded-br-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm'
                  }`}
                >
                  {ev.body || <span className="italic opacity-70">(empty)</span>}
                </div>
                <div
                  className={`flex items-center gap-1 text-[10px] text-gray-400 mt-1 px-1 ${
                    isOut ? 'justify-end' : ''
                  }`}
                >
                  <span>{relativeTime(ev.timestamp)}</span>
                  {isOut && <StatusIcon status={ev.status ?? null} />}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Sticky composer */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-3 bg-gray-50 dark:bg-gray-900/50">
        {!contactPhone ? (
          <div className="text-xs text-gray-500 dark:text-gray-400 italic">
            Add a phone number to this contact to send SMS.
          </div>
        ) : (
          <div className="flex gap-2 items-end">
            <textarea
              value={smsText}
              onChange={(e) => setSmsText(e.target.value)}
              placeholder="Type a message…"
              rows={2}
              maxLength={1600}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg resize-none bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && smsText.trim()) {
                  sendMut.mutate()
                }
              }}
            />
            <button
              onClick={() => sendMut.mutate()}
              disabled={!smsText.trim() || sendMut.isPending}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="h-4 w-4" />
              {sendMut.isPending ? 'Sending…' : 'Send'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}


/**
 * Email event bubble — distinct from SMS bubbles. Document-style
 * card with subject prominent, body snippet truncated to 2 lines
 * with a "Show more" toggle, AI summary in italic-gray below.
 *
 * Direction icons: ↗ outbound (blue), ↙ inbound (emerald). The
 * "View in Gmail" link opens the thread in a new tab (gmail.com's
 * web URL accepts the thread_id directly).
 */
function EmailEvent({ ev }: { ev: ConversationEvent }) {
  const [expanded, setExpanded] = useState(false)
  const isOut = ev.direction === 'outbound'
  const snippet = ev.snippet || ''
  const hasMore = snippet.length > 180

  return (
    <div
      className={`flex flex-col ${isOut ? 'items-end ml-auto' : 'items-start'} max-w-[88%] w-full`}
    >
      <div
        className={`w-full rounded-lg border p-3 ${
          isOut
            ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
            : 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'
        }`}
      >
        <div className="flex items-center gap-2 text-xs mb-1.5">
          {isOut ? (
            <ArrowUpRight className="h-3.5 w-3.5 text-blue-500 dark:text-blue-400 shrink-0" />
          ) : (
            <ArrowDownLeft className="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400 shrink-0" />
          )}
          <Mail
            className={`h-3.5 w-3.5 shrink-0 ${
              isOut
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-emerald-600 dark:text-emerald-400'
            }`}
          />
          <span
            className={`font-medium ${
              isOut
                ? 'text-blue-700 dark:text-blue-300'
                : 'text-emerald-700 dark:text-emerald-300'
            }`}
          >
            Email
          </span>
          <span className="text-gray-400 dark:text-gray-500">·</span>
          <span className="text-gray-500 dark:text-gray-400 text-[11px]">
            {isOut ? 'Sent' : 'Received'}
          </span>
        </div>

        {ev.subject && (
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1.5 break-words">
            {ev.subject}
          </div>
        )}

        {snippet && (
          <div
            className={`text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words ${
              expanded ? '' : 'line-clamp-2'
            }`}
          >
            {snippet}
          </div>
        )}
        {hasMore && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline mt-1"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}

        {ev.body_summary && (
          <div className="mt-2 pt-2 border-t border-white/40 dark:border-white/10">
            <div className="flex items-start gap-1.5 text-[11px] italic text-gray-600 dark:text-gray-400">
              <Sparkles className="h-3 w-3 mt-0.5 shrink-0 text-indigo-500 dark:text-indigo-400 not-italic" />
              <span>
                <span className="font-medium not-italic text-gray-500 dark:text-gray-500 mr-1">
                  AI summary:
                </span>
                {ev.body_summary}
              </span>
            </div>
          </div>
        )}

        {ev.thread_id && (
          <div className="mt-2 flex items-center gap-3">
            <a
              href={`https://mail.google.com/mail/u/0/#inbox/${ev.thread_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
            >
              View in Gmail ↗
            </a>
          </div>
        )}
      </div>
      <span className="text-[10px] text-gray-400 mt-1 px-1">
        {relativeTime(ev.timestamp)}
      </span>
    </div>
  )
}
