import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Pencil, Trash2, X, Check,
  FileText, FileSignature, Calculator,
  BookOpen, FolderOpen, Video, Activity,
  Mail, MessageSquare, Phone, StickyNote, Send,
  Plus, Tag, MapPin, User, Building2, Briefcase,
  Clock, Calendar, BellOff, Bell,
  CheckSquare, DollarSign,
  Filter,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/lib/utils'
import {
  getContact, updateContact, deleteContact,
  getContactActivities, getFileShares,
  addContactActivity, getContactTags, addContactTag,
  removeContactTag, getAllTagNames,
} from '@/api/contacts'
import { listInvoices } from '@/api/invoices'
import { listProposals } from '@/api/proposals'
import { listEstimates } from '@/api/estimates'
import { listMeetings } from '@/api/meetings'
import { listEntries } from '@/api/cashbook'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TabKey =
  | 'activity' | 'messages' | 'invoices' | 'proposals'
  | 'estimates' | 'files' | 'meetings' | 'expenses'
  | 'tasks' | 'payments'

type ComposerKey = 'email' | 'call' | 'note' | 'sms'

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'activity', label: 'Activity', icon: Activity },
  { key: 'messages', label: 'Messages', icon: MessageSquare },
  { key: 'invoices', label: 'Invoices', icon: FileText },
  { key: 'proposals', label: 'Proposals', icon: FileSignature },
  { key: 'estimates', label: 'Estimates', icon: Calculator },
  { key: 'files', label: 'Files', icon: FolderOpen },
  { key: 'meetings', label: 'Meetings', icon: Video },
  { key: 'expenses', label: 'Expenses', icon: BookOpen },
  { key: 'tasks', label: 'Tasks', icon: CheckSquare },
  { key: 'payments', label: 'Payments', icon: DollarSign },
]

const LEAD_SOURCES = [
  'Website', 'Referral', 'Social Media', 'Cold Outreach', 'Ads', 'Event', 'Other',
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    sent: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    viewed: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    paid: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    overdue: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    accepted: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    rejected: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    expired: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    converted: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    signed: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    declined: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    waiting_signature: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
    scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    in_progress: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
    completed: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    cancelled: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  }
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', colors[status] || colors.draft)}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function formatCurrency(amount: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateTime(dateStr: string) {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })
}

function getInitials(name: string | null, company: string): string {
  const source = name || company || '?'
  return source
    .split(/\s+/)
    .map(w => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function EmptyState({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icon className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{description}</p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3 py-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="animate-pulse flex items-center gap-4">
          <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="flex-1" />
          <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      ))}
    </div>
  )
}

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
// Inline Editable Field
// ---------------------------------------------------------------------------

function InlineField({
  label,
  value,
  onSave,
  type = 'text',
  placeholder,
  icon: Icon,
}: {
  label: string
  value: string
  onSave: (v: string) => void
  type?: string
  placeholder?: string
  icon?: React.ElementType
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setDraft(value) }, [value])
  useEffect(() => { if (editing) inputRef.current?.focus() }, [editing])

  const commit = () => {
    setEditing(false)
    if (draft !== value) onSave(draft)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') commit()
    if (e.key === 'Escape') { setDraft(value); setEditing(false) }
  }

  return (
    <div className="group">
      <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">
        {label}
      </label>
      {editing ? (
        <input
          ref={inputRef}
          type={type}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full px-2 py-1 text-sm border border-blue-400 dark:border-blue-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      ) : (
        <div
          onClick={() => setEditing(true)}
          className="flex items-center gap-1.5 px-2 py-1 -mx-2 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors min-h-[28px]"
        >
          {Icon && <Icon className="h-3.5 w-3.5 text-gray-400 dark:text-gray-500 shrink-0" />}
          <span className={cn('text-sm', value ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-500 italic')}>
            {value || placeholder || 'Click to add'}
          </span>
          <Pencil className="h-3 w-3 text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity ml-auto shrink-0" />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  // State
  const [activeTab, setActiveTab] = useState<TabKey>('activity')
  const [activeComposer, setActiveComposer] = useState<ComposerKey | null>(null)
  const [savedToast, setSavedToast] = useState(false)
  const [activityFilter, setActivityFilter] = useState<string>('all')

  // Composer state
  const [noteText, setNoteText] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [smsText, setSmsText] = useState('')

  // Tag state
  const [tagInput, setTagInput] = useState('')
  const [showTagSuggestions, setShowTagSuggestions] = useState(false)

  // Queries
  const { data, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  })

  const invoicesQuery = useQuery({
    queryKey: ['contact-invoices', id],
    queryFn: () => listInvoices({ contact_id: id }),
    enabled: !!id,
  })

  const proposalsQuery = useQuery({
    queryKey: ['contact-proposals', id],
    queryFn: () => listProposals({ contact_id: id }),
    enabled: !!id,
  })

  const estimatesQuery = useQuery({
    queryKey: ['contact-estimates', id],
    queryFn: () => listEstimates({ contact_id: id }),
    enabled: !!id,
  })

  const meetingsQuery = useQuery({
    queryKey: ['contact-meetings', id],
    queryFn: () => listMeetings({ contact_id: id }),
    enabled: !!id,
  })

  const filesQuery = useQuery({
    queryKey: ['contact-files', id],
    queryFn: () => getFileShares(id!),
    enabled: !!id,
  })

  const activityQuery = useQuery({
    queryKey: ['contact-activities', id],
    queryFn: () => getContactActivities(id!),
    enabled: !!id,
  })

  const expensesQuery = useQuery({
    queryKey: ['contact-expenses', id],
    queryFn: () => listEntries({ search: id }),
    enabled: !!id && activeTab === 'expenses',
  })

  const tagsQuery = useQuery({
    queryKey: ['contact-tags', id],
    queryFn: () => getContactTags(id!),
    enabled: !!id,
  })

  const allTagsQuery = useQuery({
    queryKey: ['all-tag-names'],
    queryFn: () => getAllTagNames(),
    enabled: showTagSuggestions,
  })

  // Mutations
  const updateMutation = useMutation({
    mutationFn: (updates: Record<string, any>) => updateContact(id!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', id] })
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      flashSaved()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      navigate('/contacts')
    },
  })

  const addActivityMutation = useMutation({
    mutationFn: (data: { activity_type: string; title: string; description?: string }) =>
      addContactActivity(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-activities', id] })
    },
  })

  const addTagMutation = useMutation({
    mutationFn: (tagName: string) => addContactTag(id!, tagName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-tags', id] })
    },
  })

  const removeTagMutation = useMutation({
    mutationFn: (tagName: string) => removeContactTag(id!, tagName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-tags', id] })
    },
  })

  // Helpers
  const flashSaved = useCallback(() => {
    setSavedToast(true)
    setTimeout(() => setSavedToast(false), 1500)
  }, [])

  const saveField = useCallback((key: string, value: any) => {
    updateMutation.mutate({ [key]: value || null })
  }, [updateMutation])

  const contact = data?.data

  // Extracted data
  const invoices = invoicesQuery.data?.data || []
  const proposals = proposalsQuery.data?.data || []
  const estimates = estimatesQuery.data?.data || []
  const meetings = meetingsQuery.data?.data || []
  const fileShares = (filesQuery.data as any)?.data || []
  const activities = (activityQuery.data as any)?.data || []
  const expenses = expensesQuery.data?.data || []
  const tags: any[] = (tagsQuery.data as any)?.data || []
  const allTags: string[] = (allTagsQuery.data as any)?.data || []

  const tabCounts: Partial<Record<TabKey, number>> = {
    activity: activities.length,
    invoices: invoices.length,
    proposals: proposals.length,
    estimates: estimates.length,
    files: fileShares.length,
    meetings: meetings.length,
    expenses: expenses.length,
  }

  // Filtered activities
  const filteredActivities = activityFilter === 'all'
    ? activities
    : activities.filter((a: any) => a.activity_type === activityFilter)

  // Tag suggestions
  const tagSuggestions = allTags.filter(
    t => t.toLowerCase().includes(tagInput.toLowerCase()) &&
      !tags.some((ct: any) => (ct.tag_name || ct.name || ct) === t)
  )

  // =========================================================================
  // Loading / Not Found
  // =========================================================================

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-40 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    )
  }

  if (!contact) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500 dark:text-gray-400">Contact not found</p>
        <button onClick={() => navigate('/contacts')} className="text-blue-600 dark:text-blue-400 hover:underline mt-2 text-sm">
          Back to Contacts
        </button>
      </div>
    )
  }

  const displayName = contact.contact_name || contact.company_name
  const initials = getInitials(contact.contact_name, contact.company_name)

  // =========================================================================
  // Composer handlers
  // =========================================================================

  const toggleComposer = (key: ComposerKey) => {
    setActiveComposer(prev => prev === key ? null : key)
  }

  const handleSendNote = () => {
    if (!noteText.trim()) return
    addActivityMutation.mutate({
      activity_type: 'note_added',
      title: 'Note added',
      description: noteText.trim(),
    })
    setNoteText('')
    setActiveComposer(null)
  }

  const handleSendEmail = () => {
    const subject = encodeURIComponent(emailSubject)
    const body = encodeURIComponent(emailBody)
    window.location.href = `mailto:${contact.email}?subject=${subject}&body=${body}`
    addActivityMutation.mutate({
      activity_type: 'email_sent',
      title: 'Email sent',
      description: `Subject: ${emailSubject}`,
    })
    setEmailSubject('')
    setEmailBody('')
    setActiveComposer(null)
  }

  const handleAddTag = (tagName: string) => {
    if (!tagName.trim()) return
    addTagMutation.mutate(tagName.trim())
    setTagInput('')
    setShowTagSuggestions(false)
  }

  // =========================================================================
  // Tab Renderers
  // =========================================================================

  const renderActivity = () => {
    if (activityQuery.isLoading) return <LoadingSkeleton />

    const activityTypes = [...new Set(activities.map((a: any) => a.activity_type).filter(Boolean))]

    return (
      <div className="space-y-4">
        {/* Filter bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <select
              value={activityFilter}
              onChange={e => setActivityFilter(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
            >
              <option value="all">All activities</option>
              {activityTypes.map((t: unknown, i: number) => (
                <option key={i} value={String(t)}>{String(t).replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => toggleComposer('note')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Add Note
          </button>
        </div>

        {filteredActivities.length === 0 ? (
          <EmptyState icon={Activity} title="No activity" description="No activity has been recorded for this contact yet." />
        ) : (
          <div className="relative">
            {/* Timeline line */}
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
    if (invoicesQuery.isLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/invoices/new?contact_id=${id}`)}
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
    if (proposalsQuery.isLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/proposals/new?contact_id=${id}`)}
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
    if (estimatesQuery.isLoading) return <LoadingSkeleton />
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <button
            onClick={() => navigate(`/estimates/new?contact_id=${id}`)}
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
    if (filesQuery.isLoading) return <LoadingSkeleton />
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
    if (meetingsQuery.isLoading) return <LoadingSkeleton />
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
    if (expensesQuery.isLoading) return <LoadingSkeleton />
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

  const tabContent: Record<TabKey, () => React.ReactNode> = {
    activity: renderActivity,
    messages: () => renderPlaceholder('Messages'),
    invoices: renderInvoices,
    proposals: renderProposals,
    estimates: renderEstimates,
    files: renderFiles,
    meetings: renderMeetings,
    expenses: renderExpenses,
    tasks: () => renderPlaceholder('Tasks'),
    payments: () => renderPlaceholder('Payments'),
  }

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="flex flex-col h-full">
      {/* Saved toast */}
      {savedToast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 bg-green-600 text-white text-sm rounded-lg shadow-lg animate-in fade-in slide-in-from-top-2 duration-200">
          <Check className="h-4 w-4" /> Saved
        </div>
      )}

      {/* =============================================================== */}
      {/* TOP HEADER BAR (sticky) */}
      {/* =============================================================== */}
      <div className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        {/* Row 1: Back + Name + Actions */}
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/contacts')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 truncate">
              {displayName}
            </h1>
            <div className="flex items-center gap-3 mt-0.5 flex-wrap">
              {contact.company_name && contact.contact_name && (
                <span className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
                  <Building2 className="h-3.5 w-3.5" /> {contact.company_name}
                </span>
              )}
              {contact.email && (
                <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <Mail className="h-3 w-3" /> {contact.email}
                </span>
              )}
              {contact.phone && (
                <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <Phone className="h-3 w-3" /> {contact.phone}
                </span>
              )}
            </div>
          </div>

          {canEdit && (
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => {
                  if (confirm('Delete this contact? This action cannot be undone.')) deleteMutation.mutate()
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </button>
            </div>
          )}
        </div>

        {/* Row 2: Action buttons */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => toggleComposer('email')}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              activeComposer === 'email'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40'
            )}
          >
            <Mail className="h-4 w-4" /> Email
          </button>
          <a
            href={contact.phone ? `tel:${contact.phone}` : undefined}
            onClick={contact.phone ? undefined : (e) => e.preventDefault()}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              contact.phone
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/40 cursor-pointer'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
            )}
          >
            <Phone className="h-4 w-4" /> Call
          </a>
          <button
            onClick={() => toggleComposer('note')}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              activeComposer === 'note'
                ? 'bg-yellow-500 text-white shadow-md'
                : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/40'
            )}
          >
            <StickyNote className="h-4 w-4" /> Note
          </button>
          <button
            onClick={() => toggleComposer('sms')}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              activeComposer === 'sms'
                ? 'bg-purple-600 text-white shadow-md'
                : 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/40'
            )}
          >
            <MessageSquare className="h-4 w-4" /> SMS
          </button>
        </div>
      </div>

      {/* =============================================================== */}
      {/* INLINE COMPOSERS */}
      {/* =============================================================== */}
      {activeComposer === 'email' && (
        <div className="mx-6 mt-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-400">Compose Email</h3>
            <button onClick={() => setActiveComposer(null)} className="text-blue-400 hover:text-blue-600">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-blue-600 dark:text-blue-400">To</label>
              <input
                type="email"
                value={contact.email || ''}
                readOnly
                className="w-full px-3 py-1.5 text-sm rounded border border-blue-200 dark:border-blue-700 bg-blue-100/50 dark:bg-blue-900/30 text-gray-700 dark:text-gray-300"
              />
            </div>
            <div>
              <label className="text-xs text-blue-600 dark:text-blue-400">Subject</label>
              <input
                type="text"
                value={emailSubject}
                onChange={e => setEmailSubject(e.target.value)}
                placeholder="Email subject..."
                className="w-full px-3 py-1.5 text-sm rounded border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-blue-600 dark:text-blue-400">Body</label>
              <textarea
                value={emailBody}
                onChange={e => setEmailBody(e.target.value)}
                placeholder="Write your message..."
                rows={4}
                className="w-full px-3 py-2 text-sm rounded border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setActiveComposer(null)}
                className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSendEmail}
                disabled={!contact.email}
                className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Send className="h-3.5 w-3.5" /> Send
              </button>
            </div>
          </div>
        </div>
      )}

      {activeComposer === 'note' && (
        <div className="mx-6 mt-4 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-yellow-700 dark:text-yellow-400">Add Note</h3>
            <button onClick={() => setActiveComposer(null)} className="text-yellow-400 hover:text-yellow-600">
              <X className="h-4 w-4" />
            </button>
          </div>
          <textarea
            value={noteText}
            onChange={e => setNoteText(e.target.value)}
            placeholder="Write a note about this contact..."
            rows={3}
            className="w-full px-3 py-2 text-sm rounded border border-yellow-200 dark:border-yellow-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-yellow-500 resize-none"
            autoFocus
          />
          <div className="flex gap-2 justify-end mt-2">
            <button
              onClick={() => setActiveComposer(null)}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSendNote}
              disabled={!noteText.trim() || addActivityMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-yellow-600 rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition-colors"
            >
              <Check className="h-3.5 w-3.5" /> Save Note
            </button>
          </div>
        </div>
      )}

      {activeComposer === 'sms' && (
        <div className="mx-6 mt-4 bg-purple-50 dark:bg-purple-900/10 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-purple-700 dark:text-purple-400">Send SMS</h3>
            <button onClick={() => setActiveComposer(null)} className="text-purple-400 hover:text-purple-600">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-purple-600 dark:text-purple-400">
              <Phone className="h-3 w-3" />
              <span>To: {contact.phone || 'No phone number'}</span>
            </div>
            <textarea
              value={smsText}
              onChange={e => setSmsText(e.target.value)}
              placeholder="Type your message..."
              rows={2}
              maxLength={160}
              className="w-full px-3 py-2 text-sm rounded border border-purple-200 dark:border-purple-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              autoFocus
            />
            <div className="flex items-center justify-between">
              <span className={cn(
                'text-xs',
                smsText.length > 140 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'
              )}>
                {smsText.length}/160
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveComposer(null)}
                  className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  disabled
                  className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-purple-600 rounded-lg opacity-50 cursor-not-allowed"
                  title="Configure Twilio to enable SMS"
                >
                  <Send className="h-3.5 w-3.5" /> Send
                </button>
              </div>
            </div>
            <p className="text-xs text-purple-500 dark:text-purple-400 bg-purple-100 dark:bg-purple-900/30 rounded px-2 py-1">
              SMS sending requires Twilio configuration. Contact your administrator to set up SMS.
            </p>
          </div>
        </div>
      )}

      {/* =============================================================== */}
      {/* TWO COLUMN LAYOUT */}
      {/* =============================================================== */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">

        {/* ------------------------------------------------------------- */}
        {/* LEFT COLUMN */}
        {/* ------------------------------------------------------------- */}
        <div className="w-full md:w-80 shrink-0 overflow-y-auto border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950 p-5 space-y-6">

          {/* Contact Info */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">Contact Info</h3>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-14 h-14 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-blue-700 dark:text-blue-300 text-lg font-bold shrink-0">
                {initials}
              </div>
              <div className="min-w-0">
                <InlineField
                  label="Full Name"
                  value={contact.contact_name || ''}
                  onSave={v => saveField('contact_name', v)}
                  placeholder="Add name"
                  icon={User}
                />
              </div>
            </div>

            <div className="space-y-2">
              <InlineField
                label="Email"
                value={contact.email || ''}
                onSave={v => saveField('email', v)}
                type="email"
                placeholder="Add email"
                icon={Mail}
              />
              <InlineField
                label="Phone"
                value={contact.phone || ''}
                onSave={v => saveField('phone', v)}
                type="tel"
                placeholder="Add phone"
                icon={Phone}
              />
              <InlineField
                label="Company"
                value={contact.company_name}
                onSave={v => saveField('company_name', v || contact.company_name)}
                placeholder="Company name"
                icon={Building2}
              />
              <InlineField
                label="Job Title"
                value={contact.job_title || ''}
                onSave={v => saveField('job_title', v)}
                placeholder="Add job title"
                icon={Briefcase}
              />
            </div>
          </div>

          <hr className="border-gray-200 dark:border-gray-700" />

          {/* Address */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5" /> Address
            </h3>
            <div className="space-y-2">
              <InlineField label="Street" value={contact.address_line1 || ''} onSave={v => saveField('address_line1', v)} placeholder="Street address" />
              <InlineField label="Apt/Suite" value={contact.address_line2 || ''} onSave={v => saveField('address_line2', v)} placeholder="Apt, suite, unit" />
              <InlineField label="City" value={contact.city || ''} onSave={v => saveField('city', v)} placeholder="City" />
              <InlineField label="Province/State" value={contact.state || ''} onSave={v => saveField('state', v)} placeholder="State/Province" />
              <InlineField label="Postal/ZIP" value={contact.zip_code || ''} onSave={v => saveField('zip_code', v)} placeholder="Postal code" />
              <InlineField label="Country" value={contact.country || ''} onSave={v => saveField('country', v)} placeholder="Country" />
            </div>
          </div>

          <hr className="border-gray-200 dark:border-gray-700" />

          {/* Lead Info */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">Lead Info</h3>
            <div className="space-y-3">
              {/* Type dropdown */}
              <div>
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">Type</label>
                <select
                  value={contact.type}
                  onChange={e => saveField('type', e.target.value)}
                  className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                  <option value="client">Client</option>
                  <option value="vendor">Vendor</option>
                  <option value="both">Both</option>
                </select>
              </div>

              {/* Lead source dropdown */}
              <div>
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">Lead Source</label>
                <select
                  value={contact.lead_source || ''}
                  onChange={e => saveField('lead_source', e.target.value)}
                  className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                  <option value="">-- Select --</option>
                  {LEAD_SOURCES.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              {/* Assigned user */}
              <div>
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">Assigned User</label>
                <p className="text-sm text-gray-600 dark:text-gray-400 px-2 py-1">
                  {contact.assigned_user_id || 'Unassigned'}
                </p>
              </div>
            </div>
          </div>

          <hr className="border-gray-200 dark:border-gray-700" />

          {/* Settings */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3">Settings</h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {contact.dnd_enabled ? (
                  <BellOff className="h-4 w-4 text-red-500" />
                ) : (
                  <Bell className="h-4 w-4 text-gray-400" />
                )}
                <span className="text-sm text-gray-700 dark:text-gray-300">Do Not Disturb</span>
              </div>
              <button
                onClick={() => saveField('dnd_enabled', !contact.dnd_enabled)}
                className={cn(
                  'relative w-10 h-5 rounded-full transition-colors',
                  contact.dnd_enabled ? 'bg-red-500' : 'bg-gray-300 dark:bg-gray-600'
                )}
              >
                <div className={cn(
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                  contact.dnd_enabled ? 'translate-x-5' : 'translate-x-0.5'
                )} />
              </button>
            </div>
          </div>

          <hr className="border-gray-200 dark:border-gray-700" />

          {/* Tags */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
              <Tag className="h-3.5 w-3.5" /> Tags
            </h3>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {tags.length === 0 && (
                <span className="text-xs text-gray-400 dark:text-gray-500 italic">No tags</span>
              )}
              {tags.map((t: any) => {
                const name = t.tag_name || t.name || t
                return (
                  <span
                    key={name}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                  >
                    {name}
                    <button
                      onClick={() => removeTagMutation.mutate(name)}
                      className="hover:text-red-500 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                )
              })}
            </div>
            <div className="relative">
              <input
                type="text"
                value={tagInput}
                onChange={e => { setTagInput(e.target.value); setShowTagSuggestions(true) }}
                onFocus={() => setShowTagSuggestions(true)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && tagInput.trim()) {
                    e.preventDefault()
                    handleAddTag(tagInput)
                  }
                }}
                placeholder="Add tag..."
                className="w-full px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {showTagSuggestions && tagInput && tagSuggestions.length > 0 && (
                <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg max-h-32 overflow-y-auto">
                  {tagSuggestions.slice(0, 8).map(s => (
                    <button
                      key={s}
                      onClick={() => handleAddTag(s)}
                      className="w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <hr className="border-gray-200 dark:border-gray-700" />

          {/* Dates */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-3 flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" /> Dates
            </h3>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Created</span>
                <span className="text-gray-700 dark:text-gray-300">{formatDate(contact.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Updated</span>
                <span className="text-gray-700 dark:text-gray-300">{formatDate(contact.updated_at)}</span>
              </div>
              {activities.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Last Activity</span>
                  <span className="text-gray-700 dark:text-gray-300">{formatDate(activities[0].created_at)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Tax ID / Notes */}
          <hr className="border-gray-200 dark:border-gray-700" />
          <div className="space-y-2">
            <InlineField
              label="Tax ID"
              value={contact.tax_id || ''}
              onSave={v => saveField('tax_id', v)}
              placeholder="Add tax ID"
            />
            <div>
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500 mb-0.5">Notes</label>
              <div
                onClick={() => {
                  const newNote = prompt('Notes:', contact.notes || '')
                  if (newNote !== null && newNote !== contact.notes) {
                    saveField('notes', newNote)
                  }
                }}
                className="px-2 py-1.5 text-sm rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors min-h-[32px] text-gray-700 dark:text-gray-300 whitespace-pre-wrap"
              >
                {contact.notes || <span className="text-gray-400 dark:text-gray-500 italic">Click to add notes</span>}
              </div>
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* RIGHT COLUMN */}
        {/* ------------------------------------------------------------- */}
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
                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="hidden sm:inline">{label}</span>
                    {count != null && count > 0 && (
                      <span className={cn(
                        'ml-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
                        activeTab === key
                          ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                      )}>
                        {count}
                      </span>
                    )}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-5">
            {tabContent[activeTab]()}
          </div>
        </div>
      </div>
    </div>
  )
}
