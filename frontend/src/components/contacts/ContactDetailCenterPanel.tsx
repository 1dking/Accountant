/**
 * Center column of the contact detail page: tab bar + per-tab content
 * rendering. Receives all query data + tab state from the parent page.
 *
 * Tabs in current order (pre-grid commit): Activity → Memory →
 * Messages → Invoices → Proposals → Estimates → Files → Meetings →
 * Expenses → Tasks → Payments. Order + default tab will change in
 * the subsequent layout commit; this extraction is pure mechanical
 * reorganization.
 */
import { useNavigate } from 'react-router'
import {
  Activity, BookOpen, Brain, Calculator, CheckSquare, Clock,
  DollarSign, FileSignature, FileText, Filter, FolderOpen, Mail,
  MessageSquare, Phone, Plus, StickyNote, Video,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ContactConversationThread from './ContactConversationThread'
import {
  EmptyState, LoadingSkeleton, StatusBadge,
  formatCurrency, formatDate, formatDateTime,
} from './contactDetailUtils'
import type { ContactMemory } from '@/api/automation'

// ---------------------------------------------------------------------------
// Tab metadata
// ---------------------------------------------------------------------------

export type TabKey =
  | 'activity' | 'memory' | 'messages' | 'invoices' | 'proposals'
  | 'estimates' | 'files' | 'meetings' | 'expenses'
  | 'tasks' | 'payments'

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'messages', label: 'Messages', icon: MessageSquare },
  { key: 'activity', label: 'Activity', icon: Activity },
  { key: 'memory', label: 'Memory', icon: Brain },
  { key: 'invoices', label: 'Invoices', icon: FileText },
  { key: 'proposals', label: 'Proposals', icon: FileSignature },
  { key: 'estimates', label: 'Estimates', icon: Calculator },
  { key: 'files', label: 'Files', icon: FolderOpen },
  { key: 'meetings', label: 'Meetings', icon: Video },
  { key: 'expenses', label: 'Expenses', icon: BookOpen },
  { key: 'tasks', label: 'Tasks', icon: CheckSquare },
  { key: 'payments', label: 'Payments', icon: DollarSign },
]

// Activity timeline icon + color maps (locally scoped — only used here).
const activityIcon: Record<string, React.ElementType> = {
  note_added: StickyNote,
  email_sent: Mail,
  call_made: Phone,
  meeting_scheduled: Video,
  invoice_created: FileText,
  proposal_sent: FileSignature,
  estimate_created: Calculator,
  file_shared: FolderOpen,
  sms_sent: MessageSquare,
}

const activityColor: Record<string, string> = {
  note_added: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-600 dark:text-yellow-400',
  email_sent: 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400',
  call_made: 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400',
  meeting_scheduled: 'bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400',
  invoice_created: 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400',
  proposal_sent: 'bg-pink-100 dark:bg-pink-900/40 text-pink-600 dark:text-pink-400',
  estimate_created: 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-600 dark:text-cyan-400',
  file_shared: 'bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400',
  sms_sent: 'bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-400',
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  contactId: string
  contact: any
  activeTab: TabKey
  setActiveTab: (k: TabKey) => void

  // Data
  activities: any[]
  invoices: any[]
  proposals: any[]
  estimates: any[]
  meetings: any[]
  fileShares: any[]
  expenses: any[]
  memories: ContactMemory[]

  // Loading flags
  activityIsLoading: boolean
  invoicesIsLoading: boolean
  proposalsIsLoading: boolean
  estimatesIsLoading: boolean
  meetingsIsLoading: boolean
  filesIsLoading: boolean
  expensesIsLoading: boolean
  memoriesIsLoading: boolean

  // Filter + composer state
  activityFilter: string
  setActivityFilter: (v: string) => void
  expandedMemoryId: string | null
  setExpandedMemoryId: (v: string | null) => void

  // Callbacks
  onAddNoteClick: () => void
  onAddMemoryClick: () => void
  onDeleteMemory: (id: string) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContactDetailCenterPanel(props: Props) {
  const {
    contactId, contact, activeTab, setActiveTab,
    activities, invoices, proposals, estimates, meetings,
    fileShares, expenses, memories,
    activityIsLoading, invoicesIsLoading, proposalsIsLoading,
    estimatesIsLoading, meetingsIsLoading, filesIsLoading,
    expensesIsLoading, memoriesIsLoading,
    activityFilter, setActivityFilter,
    expandedMemoryId, setExpandedMemoryId,
    onAddNoteClick, onAddMemoryClick, onDeleteMemory,
  } = props
  const navigate = useNavigate()

  const tabCounts: Partial<Record<TabKey, number>> = {
    activity: activities.length,
    invoices: invoices.length,
    proposals: proposals.length,
    estimates: estimates.length,
    files: fileShares.length,
    meetings: meetings.length,
    expenses: expenses.length,
  }

  const filteredActivities = activityFilter === 'all'
    ? activities
    : activities.filter((a: any) => a.activity_type === activityFilter)

  // -------------------------------------------------------------------------
  // Tab renderers — copied verbatim from the legacy mega-component
  // -------------------------------------------------------------------------

  const renderActivity = () => {
    if (activityIsLoading) return <LoadingSkeleton />
    const activityTypes = [...new Set(activities.map((a: any) => a.activity_type).filter(Boolean))]

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <select
              value={activityFilter}
              onChange={(e) => setActivityFilter(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
            >
              <option value="all">All activities</option>
              {activityTypes.map((t: unknown, i: number) => (
                <option key={i} value={String(t)}>{String(t).replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <button
            onClick={onAddNoteClick}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Add Note
          </button>
        </div>

        {filteredActivities.length === 0 ? (
          <EmptyState icon={Activity} title="No activity" description="No activity has been recorded for this contact yet." />
        ) : (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200 dark:bg-gray-700" />
            <div className="space-y-4">
              {filteredActivities.map((a: any) => {
                const IconComponent = activityIcon[a.activity_type] || Activity
                const colorClass = activityColor[a.activity_type] || 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                return (
                  <div key={a.id} className="flex items-start gap-3 relative pl-0">
                    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center shrink-0 z-10', colorClass)}>
                      <IconComponent className="h-3.5 w-3.5" />
                    </div>
                    <div className="flex-1 min-w-0 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-700 rounded-lg p-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{a.title}</p>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-medium">
                          {a.activity_type?.replace(/_/g, ' ') || 'note'}
                        </span>
                      </div>
                      {a.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 whitespace-pre-wrap">{a.description}</p>
                      )}
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1.5">
                        {formatDateTime(a.created_at)}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderInvoices = () => {
    if (invoicesIsLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/invoices/new?contact_id=${contactId}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Create Invoice
          </button>
        </div>
        {invoices.length === 0 ? (
          <EmptyState icon={FileText} title="No invoices" description="No invoices have been created for this contact yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
                  <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Amount</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv: any) => (
                  <tr
                    key={inv.id}
                    onClick={() => navigate(`/invoices/${inv.id}`)}
                    className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-3 font-mono text-gray-900 dark:text-gray-100">{inv.invoice_number}</td>
                    <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(inv.total, inv.currency)}</td>
                    <td className="py-2.5 px-3"><StatusBadge status={inv.status} /></td>
                    <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(inv.issue_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderProposals = () => {
    if (proposalsIsLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/proposals/new?contact_id=${contactId}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Create Proposal
          </button>
        </div>
        {proposals.length === 0 ? (
          <EmptyState icon={FileSignature} title="No proposals" description="No proposals have been created for this contact yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Title</th>
                  <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Value</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
                </tr>
              </thead>
              <tbody>
                {proposals.map((p: any) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/proposals/${p.id}`)}
                    className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-3 text-gray-900 dark:text-gray-100 max-w-[200px] truncate">{p.title}</td>
                    <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(p.value, p.currency)}</td>
                    <td className="py-2.5 px-3"><StatusBadge status={p.status} /></td>
                    <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderEstimates = () => {
    if (estimatesIsLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/estimates/new?contact_id=${contactId}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Create Estimate
          </button>
        </div>
        {estimates.length === 0 ? (
          <EmptyState icon={Calculator} title="No estimates" description="No estimates have been created for this contact yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
                  <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Total</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
                </tr>
              </thead>
              <tbody>
                {estimates.map((est: any) => (
                  <tr
                    key={est.id}
                    onClick={() => navigate(`/estimates/${est.id}`)}
                    className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-3 font-mono text-gray-900 dark:text-gray-100">{est.estimate_number}</td>
                    <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(est.total, est.currency)}</td>
                    <td className="py-2.5 px-3"><StatusBadge status={est.status} /></td>
                    <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(est.issue_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderFiles = () => {
    if (filesIsLoading) return <LoadingSkeleton />
    if (fileShares.length === 0) return <EmptyState icon={FolderOpen} title="No shared files" description="No files have been shared with this contact yet." />
    return (
      <div className="space-y-2">
        {fileShares.map((share: any) => (
          <div
            key={share.id}
            className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors border border-gray-100 dark:border-gray-700"
          >
            <div className="flex items-center gap-3 min-w-0">
              <FolderOpen className="h-4 w-4 text-gray-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-gray-900 dark:text-gray-100 truncate">
                  {share.file_name || share.document_title || `File ${share.file_id?.slice(0, 8)}`}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">{share.permission} access</p>
              </div>
            </div>
            {share.created_at && (
              <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 ml-3">{formatDate(share.created_at)}</span>
            )}
          </div>
        ))}
      </div>
    )
  }

  const renderMeetings = () => {
    if (meetingsIsLoading) return <LoadingSkeleton />
    if (meetings.length === 0) return <EmptyState icon={Video} title="No meetings" description="No meetings have been scheduled with this contact yet." />
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Title</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
            </tr>
          </thead>
          <tbody>
            {meetings.map((m: any) => (
              <tr
                key={m.id}
                onClick={() => navigate(`/meetings/${m.id}`)}
                className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
              >
                <td className="py-2.5 px-3 text-gray-900 dark:text-gray-100">{m.title}</td>
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(m.scheduled_start)}</td>
                <td className="py-2.5 px-3"><StatusBadge status={m.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderExpenses = () => {
    if (expensesIsLoading) return <LoadingSkeleton />
    if (expenses.length === 0) return <EmptyState icon={BookOpen} title="No expenses" description="No cashbook entries found for this contact." />
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Description</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Type</th>
              <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Amount</th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((e: any) => (
              <tr key={e.id} className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(e.date)}</td>
                <td className="py-2.5 px-3 text-gray-900 dark:text-gray-100">{e.description}</td>
                <td className="py-2.5 px-3"><StatusBadge status={e.entry_type} /></td>
                <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(e.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderPlaceholder = (title: string) => (
    <EmptyState icon={Clock} title={`${title} coming soon`} description={`The ${title.toLowerCase()} tab will be available in a future update.`} />
  )

  const renderMemory = () => {
    const sourceIcon = (src: string) => {
      if (src === 'voicemail') return '🎙'
      if (src === 'sms_thread') return '💬'
      if (src === 'voice_call') return '📞'
      return '📝'
    }
    return (
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Contact memory (AI-extracted)
          </h3>
          <button
            onClick={onAddMemoryClick}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-md flex items-center gap-1"
          >
            <Plus className="h-3 w-3" /> Add manual memory
          </button>
        </div>

        {memoriesIsLoading ? (
          <div className="text-sm text-gray-500">Loading…</div>
        ) : memories.length === 0 ? (
          <EmptyState
            icon={Brain}
            title="No memory yet"
            description="Voicemails and conversations with this contact will appear here as AI-extracted summaries."
          />
        ) : (
          <div className="space-y-2">
            {memories.map((m) => {
              const isExpanded = expandedMemoryId === m.id
              return (
                <div
                  key={m.id}
                  className="border border-gray-200 dark:border-gray-700 rounded-md p-3 bg-white dark:bg-gray-900"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-base">{sourceIcon(m.source_type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                        <span className="font-medium capitalize">
                          {m.source_type.replace('_', ' ')}
                        </span>
                        <span>·</span>
                        <span>{m.created_at ? formatDateTime(m.created_at) : ''}</span>
                      </div>
                      <div className="text-sm text-gray-900 dark:text-gray-100">
                        {m.summary || <span className="italic text-gray-400">No summary</span>}
                      </div>
                      {isExpanded && (
                        <div className="mt-2 space-y-1.5 text-xs">
                          {m.commitments && (
                            <div>
                              <span className="font-semibold text-gray-700 dark:text-gray-300">Commitments:</span>{' '}
                              <span className="text-gray-600 dark:text-gray-400">{m.commitments}</span>
                            </div>
                          )}
                          {m.cares_about && (
                            <div>
                              <span className="font-semibold text-gray-700 dark:text-gray-300">Cares about:</span>{' '}
                              <span className="text-gray-600 dark:text-gray-400">{m.cares_about}</span>
                            </div>
                          )}
                          {m.talking_points && (
                            <div>
                              <span className="font-semibold text-gray-700 dark:text-gray-300">Next time:</span>{' '}
                              <span className="text-gray-600 dark:text-gray-400">{m.talking_points}</span>
                            </div>
                          )}
                          {m.raw_input && (
                            <details className="mt-2">
                              <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                                Raw input
                              </summary>
                              <pre className="mt-1 whitespace-pre-wrap text-gray-500 dark:text-gray-400 text-xs">
                                {m.raw_input}
                              </pre>
                            </details>
                          )}
                        </div>
                      )}
                      <div className="flex gap-3 mt-2 text-xs">
                        <button
                          onClick={() => setExpandedMemoryId(isExpanded ? null : m.id)}
                          className="text-blue-600 hover:underline"
                        >
                          {isExpanded ? 'Collapse' : 'Show details'}
                        </button>
                        <button
                          onClick={() => {
                            if (confirm('Delete this memory entry?')) {
                              onDeleteMemory(m.id)
                            }
                          }}
                          className="text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  const tabContent: Record<TabKey, () => React.ReactNode> = {
    activity: renderActivity,
    memory: renderMemory,
    messages: () => (
      <ContactConversationThread
        contactId={contactId}
        contactPhone={contact?.phone}
        contactEngineEnabled={contact?.conversation_engine_enabled ?? null}
        contactEnginePausedUntil={contact?.conversation_engine_paused_until ?? null}
      />
    ),
    invoices: renderInvoices,
    proposals: renderProposals,
    estimates: renderEstimates,
    files: renderFiles,
    meetings: renderMeetings,
    expenses: renderExpenses,
    tasks: () => renderPlaceholder('Tasks'),
    payments: () => renderPlaceholder('Payments'),
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Tab bar */}
      <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-x-auto shrink-0">
        <nav className="flex gap-0 -mb-px px-4" aria-label="Contact tabs">
          {TABS.map(({ key, label, icon: Icon }) => {
            const count = tabCounts[key]
            return (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors',
                  activeTab === key
                    ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600',
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
                {count != null && count > 0 && (
                  <span
                    className={cn(
                      'ml-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
                      activeTab === key
                        ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400',
                    )}
                  >
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {tabContent[activeTab]()}
      </div>
    </div>
  )
}
