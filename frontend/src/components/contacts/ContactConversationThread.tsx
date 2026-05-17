import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Send, Voicemail, AlertCircle, Check, Phone } from 'lucide-react'
import {
  listContactConversations,
  sendSms,
  type ConversationEvent,
} from '@/api/communication'

interface Props {
  contactId: string
  contactPhone: string | null | undefined
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

export default function ContactConversationThread({ contactId, contactPhone }: Props) {
  const queryClient = useQueryClient()
  const [smsText, setSmsText] = useState('')
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [isTabVisible, setIsTabVisible] = useState(
    typeof document !== 'undefined' ? document.visibilityState === 'visible' : true,
  )

  useEffect(() => {
    const onVis = () => setIsTabVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

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
                  {isOut && <StatusIcon status={ev.status} />}
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
