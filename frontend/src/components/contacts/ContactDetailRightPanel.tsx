/**
 * Right column of the contact detail page: at-a-glance context.
 *
 * Stack of 4 cards (Files intentionally excluded — it stays as a
 * center-panel tab; right panel is for *glance-at-it* context, not
 * destinations):
 *
 *   1. AI Brief — reuses existing ContactAIBrief component (with a
 *      `compact` flag here so the panel-side render doesn't carry
 *      the legacy mx-6 margin used when it rendered above the columns).
 *   2. Recent Memories — top 3 from the memories query.
 *   3. Quick Actions — Email / Call / Note buttons that fan out to
 *      the same handlers the top header uses (passed in via props).
 *   4. Recent Activity — top 5 from the activity feed.
 *
 * Each card "View all in <Tab> tab" link calls `onSwitchTab` so the
 * center panel jumps to the relevant tab — no full-page navigation.
 */
import { Activity, Brain, Mail, MessageSquare, Phone, Sparkles, StickyNote } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getContactBrief, regenerateContactBrief, type ContactMemory } from '@/api/automation'
import { formatDateTime } from './contactDetailUtils'
import type { TabKey } from './ContactDetailCenterPanel'

function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const diffMs = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  return `${day}d ago`
}

function memorySourceIcon(src: string): string {
  if (src === 'voicemail') return '🎙'
  if (src === 'sms_thread') return '💬'
  if (src === 'voice_call') return '📞'
  return '📝'
}

const activityShortIcon: Record<string, React.ElementType> = {
  note_added: StickyNote,
  email_sent: Mail,
  call_made: Phone,
  sms_sent: MessageSquare,
}

interface Props {
  contactId: string
  contactPhone: string | null
  contactEmail: string | null
  memories: ContactMemory[]
  activities: any[]
  onSwitchTab: (tab: TabKey) => void
  onEmailClick: () => void
  onNoteClick: () => void
}

function Card({
  title,
  icon: Icon,
  iconColor,
  action,
  children,
}: {
  title: string
  icon: React.ElementType
  iconColor?: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Icon className={cn('h-3.5 w-3.5', iconColor || 'text-gray-400')} />
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            {title}
          </h3>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

// ---------------------------------------------------------------------------
// AI Brief sub-card — local lightweight variant (the original
// ContactAIBrief component uses mx-6 margins for the legacy top-of-page
// render). Same data + same regen mutation.
// ---------------------------------------------------------------------------

function AIBriefCard({ contactId }: { contactId: string }) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['contact-brief', contactId],
    queryFn: () => getContactBrief(contactId),
    enabled: !!contactId,
    staleTime: 60_000,
  })

  const regenMut = useMutation({
    mutationFn: () => regenerateContactBrief(contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-brief', contactId] })
      toast.success('Brief refreshed')
    },
    onError: (e: any) => toast.error(`Brief refresh failed: ${e.message || ''}`),
  })

  const brief = data?.data?.brief
  const generated = data?.data?.generated_at
  const isFresh = data?.data?.is_fresh

  return (
    <Card
      title="AI Brief"
      icon={Sparkles}
      iconColor="text-indigo-500 dark:text-indigo-400"
      action={
        <button
          onClick={() => regenMut.mutate()}
          disabled={regenMut.isPending}
          className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline disabled:opacity-50"
          title="Regenerate brief"
        >
          {regenMut.isPending ? 'Refreshing…' : 'Refresh'}
        </button>
      }
    >
      {isLoading ? (
        <p className="text-xs text-gray-500 dark:text-gray-400">Generating…</p>
      ) : isError ? (
        <p className="text-xs text-red-500 dark:text-red-400">Brief unavailable.</p>
      ) : !brief ? (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          No brief yet. Add a memory or message to generate context.
        </p>
      ) : (
        <>
          <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
            {brief}
          </p>
          {generated && (
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-2">
              {isFresh ? 'Generated' : 'Cached'} {relativeTime(generated)}
            </p>
          )}
        </>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContactDetailRightPanel({
  contactId,
  contactPhone,
  contactEmail,
  memories,
  activities,
  onSwitchTab,
  onEmailClick,
  onNoteClick,
}: Props) {
  const recentMemories = memories.slice(0, 3)
  const recentActivities = activities.slice(0, 5)

  return (
    <aside className="w-full lg:w-80 shrink-0 overflow-y-auto border-l border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950 p-3 space-y-3">

      {/* 1. AI Brief */}
      <AIBriefCard contactId={contactId} />

      {/* 2. Recent Memories */}
      <Card
        title="Recent Memories"
        icon={Brain}
        iconColor="text-purple-500 dark:text-purple-400"
        action={
          <button
            onClick={() => onSwitchTab('memory')}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            View all
          </button>
        }
      >
        {recentMemories.length === 0 ? (
          <p className="text-xs text-gray-500 dark:text-gray-400 italic">No memories yet</p>
        ) : (
          <ul className="space-y-2">
            {recentMemories.map((m) => (
              <li key={m.id} className="text-xs">
                <div className="flex items-start gap-1.5">
                  <span className="text-sm">{memorySourceIcon(m.source_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 dark:text-gray-300 line-clamp-2">
                      {m.summary || <span className="italic text-gray-400">No summary</span>}
                    </p>
                    <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                      {m.created_at ? formatDateTime(m.created_at) : ''}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* 3. Quick Actions */}
      <Card title="Quick Actions" icon={MessageSquare} iconColor="text-blue-500 dark:text-blue-400">
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={onEmailClick}
            disabled={!contactEmail}
            title={contactEmail || 'No email on file'}
            className="flex flex-col items-center gap-1 px-2 py-2 rounded-md text-xs font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Mail className="h-4 w-4" />
            Email
          </button>
          <a
            href={contactPhone ? `tel:${contactPhone}` : undefined}
            onClick={contactPhone ? undefined : (e) => e.preventDefault()}
            title={contactPhone || 'No phone on file'}
            className={cn(
              'flex flex-col items-center gap-1 px-2 py-2 rounded-md text-xs font-medium transition-colors',
              contactPhone
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/40 cursor-pointer'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed',
            )}
          >
            <Phone className="h-4 w-4" />
            Call
          </a>
          <button
            onClick={onNoteClick}
            className="flex flex-col items-center gap-1 px-2 py-2 rounded-md text-xs font-medium bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors"
          >
            <StickyNote className="h-4 w-4" />
            Note
          </button>
        </div>
      </Card>

      {/* 4. Recent Activity */}
      <Card
        title="Recent Activity"
        icon={Activity}
        iconColor="text-orange-500 dark:text-orange-400"
        action={
          <button
            onClick={() => onSwitchTab('activity')}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            View all
          </button>
        }
      >
        {recentActivities.length === 0 ? (
          <p className="text-xs text-gray-500 dark:text-gray-400 italic">No activity yet</p>
        ) : (
          <ul className="space-y-2">
            {recentActivities.map((a: any) => {
              const Icon = activityShortIcon[a.activity_type] || Activity
              return (
                <li key={a.id} className="flex items-start gap-2 text-xs">
                  <Icon className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 dark:text-gray-300 truncate">{a.title}</p>
                    <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                      {a.created_at ? relativeTime(a.created_at) : ''}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </aside>
  )
}
