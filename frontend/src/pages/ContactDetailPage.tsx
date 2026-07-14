import { useCallback, useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Check, Mail, MessageSquare, Phone, Send, Share2, StickyNote,
  Trash2, X,
} from 'lucide-react'
import ContactShareDialog from '@/components/contacts/ContactShareDialog'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/lib/utils'
import {
  addContactActivity, addContactTag, deleteContact, getAllTagNames,
  getContact, getContactActivities, getContactPayments, getContactTags, getFileShares,
  removeContactTag, updateContact,
} from '@/api/contacts'
import { listInvoices } from '@/api/invoices'
import { listProposals } from '@/api/proposals'
import { listEstimates } from '@/api/estimates'
import { listMeetings } from '@/api/meetings'
import { listEntries } from '@/api/cashbook'
import {
  createContactMemory, deleteContactMemory, listContactMemories,
  type ContactMemory,
} from '@/api/automation'
import ContactDetailLeftPanel from '@/components/contacts/ContactDetailLeftPanel'
import ContactDetailCenterPanel, {
  type TabKey,
} from '@/components/contacts/ContactDetailCenterPanel'
import ContactDetailRightPanel from '@/components/contacts/ContactDetailRightPanel'

type MobileView = 'info' | 'messages' | 'context'

type ComposerKey = 'email' | 'call' | 'note' | 'sms'

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------

  const [activeTab, setActiveTab] = useState<TabKey>('messages')
  const [mobileView, setMobileView] = useState<MobileView>('messages')
  const [activeComposer, setActiveComposer] = useState<ComposerKey | null>(null)
  const [savedToast, setSavedToast] = useState(false)
  const [activityFilter, setActivityFilter] = useState<string>('all')
  const [showMemoryModal, setShowMemoryModal] = useState(false)
  const [showShareDialog, setShowShareDialog] = useState(false)
  const [memoryDraft, setMemoryDraft] = useState('')
  const [expandedMemoryId, setExpandedMemoryId] = useState<string | null>(null)

  const [noteText, setNoteText] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')

  const [tagInput, setTagInput] = useState('')
  const [showTagSuggestions, setShowTagSuggestions] = useState(false)

  // -------------------------------------------------------------------------
  // Queries
  // -------------------------------------------------------------------------

  const { data, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  })

  const memoriesQuery = useQuery({
    queryKey: ['contact-memories', id],
    queryFn: () => listContactMemories(id!),
    enabled: !!id && activeTab === 'memory',
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

  const paymentsQuery = useQuery({
    queryKey: ['contact-payments', id],
    queryFn: () => getContactPayments(id!),
    enabled: !!id && activeTab === 'payments',
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

  // -------------------------------------------------------------------------
  // Mutations
  // -------------------------------------------------------------------------

  const flashSaved = useCallback(() => {
    setSavedToast(true)
    setTimeout(() => setSavedToast(false), 1500)
  }, [])

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
    mutationFn: (payload: { activity_type: string; title: string; description?: string }) =>
      addContactActivity(id!, payload),
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

  const createMemoryMut = useMutation({
    mutationFn: (raw: string) => createContactMemory(id!, raw),
    onSuccess: () => {
      setShowMemoryModal(false)
      setMemoryDraft('')
      queryClient.invalidateQueries({ queryKey: ['contact-memories', id] })
    },
  })

  const deleteMemoryMut = useMutation({
    mutationFn: (memoryId: string) => deleteContactMemory(id!, memoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-memories', id] })
    },
  })

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  const contact = data?.data
  const invoices = invoicesQuery.data?.data || []
  const proposals = proposalsQuery.data?.data || []
  const estimates = estimatesQuery.data?.data || []
  const meetings = meetingsQuery.data?.data || []
  const fileShares = (filesQuery.data as any)?.data || []
  const activities = (activityQuery.data as any)?.data || []
  const expenses = expensesQuery.data?.data || []
  const payments = paymentsQuery.data?.data || []
  const tags: any[] = (tagsQuery.data as any)?.data || []
  const allTags: string[] = (allTagsQuery.data as any)?.data || []
  const memories: ContactMemory[] = (memoriesQuery.data?.data || []) as ContactMemory[]

  const tagSuggestions = allTags.filter(
    (t) => t.toLowerCase().includes(tagInput.toLowerCase()) &&
      !tags.some((ct: any) => (ct.tag_name || ct.name || ct) === t),
  )

  // -------------------------------------------------------------------------
  // Loading / Not Found
  // -------------------------------------------------------------------------

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

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const saveField = (key: string, value: any) => {
    updateMutation.mutate({ [key]: value || null })
  }

  const toggleComposer = (key: ComposerKey) => {
    setActiveComposer((prev) => (prev === key ? null : key))
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

  // SMS button (mobile + header) routes to Messages tab. On mobile,
  // it also flips the meta-view since panels are stacked.
  const goToMessages = () => {
    setActiveTab('messages')
    setMobileView('messages')
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {savedToast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 bg-green-600 text-white text-sm rounded-lg shadow-lg animate-in fade-in slide-in-from-top-2 duration-200">
          <Check className="h-4 w-4" /> Saved
        </div>
      )}

      {/* Sticky header */}
      <div className="sticky top-0 z-30 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/contacts')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 truncate">{displayName}</h1>
            <div className="flex items-center gap-3 mt-0.5 flex-wrap">
              {contact.company_name && contact.contact_name && (
                <span className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
                  {contact.company_name}
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

          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => setShowShareDialog(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <Share2 className="h-3.5 w-3.5" /> Share
            </button>
            {canEdit && (
              <button
                onClick={() => {
                  if (confirm('Delete this contact? This action cannot be undone.')) deleteMutation.mutate()
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </button>
            )}
          </div>
        </div>

        {/* Quick-action buttons */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => toggleComposer('email')}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              activeComposer === 'email'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40',
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
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed',
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
                : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/40',
            )}
          >
            <StickyNote className="h-4 w-4" /> Note
          </button>
          <button
            onClick={goToMessages}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              activeTab === 'messages'
                ? 'bg-purple-600 text-white shadow-md'
                : 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/40',
            )}
          >
            <MessageSquare className="h-4 w-4" /> SMS
          </button>
        </div>
      </div>

      {/* Inline composers — preserved from legacy layout */}
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
                onChange={(e) => setEmailSubject(e.target.value)}
                placeholder="Email subject..."
                className="w-full px-3 py-1.5 text-sm rounded border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-blue-600 dark:text-blue-400">Body</label>
              <textarea
                value={emailBody}
                onChange={(e) => setEmailBody(e.target.value)}
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
            onChange={(e) => setNoteText(e.target.value)}
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

      {/* Mobile/tablet meta-tabs — switch which panel is visible at
          <lg widths. Hidden on lg+ where all three are visible in the
          grid simultaneously. */}
      <nav
        className="lg:hidden flex shrink-0 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
        aria-label="Panel selector"
      >
        {([
          { key: 'messages' as const, label: 'Messages' },
          { key: 'info' as const, label: 'Info' },
          { key: 'context' as const, label: 'Context' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setMobileView(key)}
            className={cn(
              'flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors',
              mobileView === key
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
            )}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* Three-panel grid on lg+, single-column with meta-tab routing
          below lg. Each panel ignores the mobile view at lg (always
          shown via lg:flex/lg:block) and otherwise visibility-gates
          on the mobileView state. */}
      <div className="flex-1 lg:grid lg:grid-cols-[280px_1fr_320px] overflow-hidden">

        <div
          className={cn(
            'lg:flex lg:flex-col',
            mobileView === 'info' ? 'flex flex-col' : 'hidden',
          )}
        >
          <ContactDetailLeftPanel
            contact={contact}
            tags={tags}
            allTags={allTags}
            tagInput={tagInput}
            setTagInput={setTagInput}
            showTagSuggestions={showTagSuggestions}
            setShowTagSuggestions={setShowTagSuggestions}
            tagSuggestions={tagSuggestions}
            activities={activities}
            saveField={saveField}
            onAddTag={handleAddTag}
            onRemoveTag={(name) => removeTagMutation.mutate(name)}
          />
        </div>

        <div
          className={cn(
            'lg:flex lg:flex-col min-w-0',
            mobileView === 'messages' ? 'flex flex-col' : 'hidden',
          )}
        >
          <ContactDetailCenterPanel
            contactId={id!}
            contact={contact}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            activities={activities}
            invoices={invoices}
            proposals={proposals}
            estimates={estimates}
            meetings={meetings}
            fileShares={fileShares}
            expenses={expenses}
            payments={payments}
            memories={memories}
            activityIsLoading={activityQuery.isLoading}
            invoicesIsLoading={invoicesQuery.isLoading}
            proposalsIsLoading={proposalsQuery.isLoading}
            estimatesIsLoading={estimatesQuery.isLoading}
            meetingsIsLoading={meetingsQuery.isLoading}
            filesIsLoading={filesQuery.isLoading}
            expensesIsLoading={expensesQuery.isLoading}
            paymentsIsLoading={paymentsQuery.isLoading}
            memoriesIsLoading={memoriesQuery.isLoading}
            activityFilter={activityFilter}
            setActivityFilter={setActivityFilter}
            expandedMemoryId={expandedMemoryId}
            setExpandedMemoryId={setExpandedMemoryId}
            onAddNoteClick={() => toggleComposer('note')}
            onAddMemoryClick={() => setShowMemoryModal(true)}
            onDeleteMemory={(memoryId) => deleteMemoryMut.mutate(memoryId)}
          />
        </div>

        <div
          className={cn(
            'lg:block',
            mobileView === 'context' ? 'block' : 'hidden',
          )}
        >
          <ContactDetailRightPanel
            contactId={id!}
            contactPhone={contact.phone || null}
            contactEmail={contact.email || null}
            memories={memories}
            activities={activities}
            onSwitchTab={(tab) => {
              setActiveTab(tab)
              setMobileView('messages')
            }}
            onEmailClick={() => {
              toggleComposer('email')
              setMobileView('messages')
            }}
            onNoteClick={() => {
              toggleComposer('note')
              setMobileView('messages')
            }}
          />
        </div>
      </div>

      <ContactShareDialog
        contactId={id!}
        contactName={contact.company_name}
        isOpen={showShareDialog}
        onClose={() => setShowShareDialog(false)}
      />

      {/* Memory modal — owned here because state lives at page level */}
      {showMemoryModal && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setShowMemoryModal(false)}
        >
          <div
            className="bg-white dark:bg-gray-900 rounded-lg p-5 max-w-lg w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-medium mb-3">Add memory</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              Paste a meeting note, call summary, or any conversation snippet.
              AI will extract structured fields.
            </p>
            <textarea
              value={memoryDraft}
              onChange={(e) => setMemoryDraft(e.target.value.slice(0, 10000))}
              rows={6}
              placeholder="What was discussed?"
              className="w-full px-3 py-2 border rounded-md text-sm resize-none dark:bg-gray-900 dark:border-gray-600"
            />
            <div className="flex justify-between items-center mt-3">
              <span className="text-xs text-gray-500">{memoryDraft.length}/10000</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowMemoryModal(false)}
                  className="px-3 py-1.5 border rounded-md text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => memoryDraft.trim() && createMemoryMut.mutate(memoryDraft.trim())}
                  disabled={!memoryDraft.trim() || createMemoryMut.isPending}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm disabled:opacity-50"
                >
                  {createMemoryMut.isPending ? 'Extracting…' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
