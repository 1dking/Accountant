import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Pencil, Trash2, X, Check,
  LayoutDashboard, FileText, FileSignature, Calculator,
  BookOpen, FolderOpen, Video, Activity,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { getContact, updateContact, deleteContact, getContactActivities, getFileShares } from '@/api/contacts'
import { listInvoices } from '@/api/invoices'
import { listProposals } from '@/api/proposals'
import { listEstimates } from '@/api/estimates'
import { listMeetings } from '@/api/meetings'

type TabKey = 'overview' | 'invoices' | 'proposals' | 'estimates' | 'cashbook' | 'files' | 'meetings' | 'activity'

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'invoices', label: 'Invoices', icon: FileText },
  { key: 'proposals', label: 'Proposals', icon: FileSignature },
  { key: 'estimates', label: 'Estimates', icon: Calculator },
  { key: 'cashbook', label: 'Cashbook', icon: BookOpen },
  { key: 'files', label: 'Files', icon: FolderOpen },
  { key: 'meetings', label: 'Meetings', icon: Video },
  { key: 'activity', label: 'Activity', icon: Activity },
]

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
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || colors.draft}`}>
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

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const [editing, setEditing] = useState(false)
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  const { data, isLoading } = useQuery({
    queryKey: ['contact', id],
    queryFn: () => getContact(id!),
    enabled: !!id,
  })

  // Tab data queries -- only fetch when the relevant tab is active
  const invoicesQuery = useQuery({
    queryKey: ['contact-invoices', id],
    queryFn: () => listInvoices({ contact_id: id }),
    enabled: !!id && (activeTab === 'invoices' || activeTab === 'overview'),
  })

  const proposalsQuery = useQuery({
    queryKey: ['contact-proposals', id],
    queryFn: () => listProposals({ contact_id: id }),
    enabled: !!id && (activeTab === 'proposals' || activeTab === 'overview'),
  })

  const estimatesQuery = useQuery({
    queryKey: ['contact-estimates', id],
    queryFn: () => listEstimates({ contact_id: id }),
    enabled: !!id && (activeTab === 'estimates' || activeTab === 'overview'),
  })

  const meetingsQuery = useQuery({
    queryKey: ['contact-meetings', id],
    queryFn: () => listMeetings({ contact_id: id }),
    enabled: !!id && (activeTab === 'meetings' || activeTab === 'overview'),
  })

  const filesQuery = useQuery({
    queryKey: ['contact-files', id],
    queryFn: () => getFileShares(id!),
    enabled: !!id && (activeTab === 'files' || activeTab === 'overview'),
  })

  const activityQuery = useQuery({
    queryKey: ['contact-activities', id],
    queryFn: () => getContactActivities(id!),
    enabled: !!id && (activeTab === 'activity' || activeTab === 'overview'),
  })

  const updateMutation = useMutation({
    mutationFn: (updates: Record<string, any>) => updateContact(id!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', id] })
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      setEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteContact(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      navigate('/contacts')
    },
  })

  const contact = data?.data

  if (isLoading) {
    return <div className="p-6"><div className="animate-pulse h-8 w-48 bg-gray-200 dark:bg-gray-700 rounded" /></div>
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

  const startEditing = () => {
    setFormData({
      type: contact.type,
      company_name: contact.company_name,
      contact_name: contact.contact_name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      address_line1: contact.address_line1 || '',
      address_line2: contact.address_line2 || '',
      city: contact.city || '',
      state: contact.state || '',
      zip_code: contact.zip_code || '',
      country: contact.country,
      tax_id: contact.tax_id || '',
      notes: contact.notes || '',
    })
    setEditing(true)
  }

  const saveEdit = () => {
    const updates: Record<string, any> = {}
    for (const [key, value] of Object.entries(formData)) {
      if (value !== '' || key === 'company_name') {
        updates[key] = value || null
      }
    }
    updates.company_name = formData.company_name
    updates.type = formData.type
    updates.country = formData.country || 'US'
    updateMutation.mutate(updates)
  }

  const field = (label: string, key: string, type = 'text') => (
    <div>
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      {editing ? (
        key === 'type' ? (
          <select
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="client">Client</option>
            <option value="vendor">Vendor</option>
            <option value="both">Client & Vendor</option>
          </select>
        ) : key === 'notes' ? (
          <textarea
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : (
          <input
            type={type}
            value={formData[key] || ''}
            onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )
      ) : (
        <p className="text-sm text-gray-900 dark:text-gray-100">
          {key === 'type'
            ? (contact as any)[key] === 'both' ? 'Client & Vendor' : ((contact as any)[key] as string)?.charAt(0).toUpperCase() + ((contact as any)[key] as string)?.slice(1)
            : (contact as any)[key] || '\u2014'}
        </p>
      )}
    </div>
  )

  // Extracted data
  const invoices = invoicesQuery.data?.data || []
  const proposals = proposalsQuery.data?.data || []
  const estimates = estimatesQuery.data?.data || []
  const meetings = meetingsQuery.data?.data || []
  const fileShares = filesQuery.data?.data || []
  const activities = activityQuery.data?.data || []

  // Tab content renderers
  const renderOverview = () => (
    <div className="space-y-6">
      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{invoices.length}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Invoices</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{proposals.length}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Proposals</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{estimates.length}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Estimates</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{meetings.length}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Meetings</p>
        </div>
      </div>

      {/* Recent activity */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Recent Activity</h4>
        {activities.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">No recent activity</p>
        ) : (
          <div className="space-y-2">
            {activities.slice(0, 5).map((a: any) => (
              <div key={a.id} className="flex items-start gap-3 text-sm">
                <div className="w-1.5 h-1.5 mt-1.5 rounded-full bg-blue-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-gray-900 dark:text-gray-100 font-medium">{a.title}</p>
                  {a.description && <p className="text-gray-500 dark:text-gray-400 text-xs truncate">{a.description}</p>}
                </div>
                <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{formatDate(a.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent invoices */}
      {invoices.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Recent Invoices</h4>
            <button onClick={() => setActiveTab('invoices')} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">
              View all
            </button>
          </div>
          <div className="space-y-2">
            {invoices.slice(0, 3).map((inv: any) => (
              <div
                key={inv.id}
                onClick={() => navigate(`/invoices/${inv.id}`)}
                className="flex items-center justify-between p-2.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono text-gray-600 dark:text-gray-300">{inv.invoice_number}</span>
                  <StatusBadge status={inv.status} />
                </div>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{formatCurrency(inv.total, inv.currency)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )

  const renderInvoices = () => {
    if (invoicesQuery.isLoading) return <LoadingSkeleton />
    if (invoices.length === 0) return <EmptyState icon={FileText} title="No invoices" description="No invoices have been created for this contact yet." />
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Number</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Due</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
              <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Total</th>
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
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(inv.issue_date)}</td>
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(inv.due_date)}</td>
                <td className="py-2.5 px-3"><StatusBadge status={inv.status} /></td>
                <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(inv.total, inv.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderProposals = () => {
    if (proposalsQuery.isLoading) return <LoadingSkeleton />
    if (proposals.length === 0) return <EmptyState icon={FileSignature} title="No proposals" description="No proposals have been created for this contact yet." />
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Number</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Title</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
              <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Value</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Created</th>
            </tr>
          </thead>
          <tbody>
            {proposals.map((p: any) => (
              <tr
                key={p.id}
                onClick={() => navigate(`/proposals/${p.id}`)}
                className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
              >
                <td className="py-2.5 px-3 font-mono text-gray-900 dark:text-gray-100">{p.proposal_number}</td>
                <td className="py-2.5 px-3 text-gray-900 dark:text-gray-100 max-w-[200px] truncate">{p.title}</td>
                <td className="py-2.5 px-3"><StatusBadge status={p.status} /></td>
                <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(p.value, p.currency)}</td>
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(p.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderEstimates = () => {
    if (estimatesQuery.isLoading) return <LoadingSkeleton />
    if (estimates.length === 0) return <EmptyState icon={Calculator} title="No estimates" description="No estimates have been created for this contact yet." />
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Number</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Expiry</th>
              <th className="text-left py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
              <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Total</th>
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
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(est.issue_date)}</td>
                <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">{formatDate(est.expiry_date)}</td>
                <td className="py-2.5 px-3"><StatusBadge status={est.status} /></td>
                <td className="py-2.5 px-3 text-right font-medium text-gray-900 dark:text-gray-100">{formatCurrency(est.total, est.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderCashbook = () => (
    <EmptyState
      icon={BookOpen}
      title="Cashbook entries"
      description="Contact-linked cashbook entries will be available in a future update."
    />
  )

  const renderFiles = () => {
    if (filesQuery.isLoading) return <LoadingSkeleton />
    if (fileShares.length === 0) return <EmptyState icon={FolderOpen} title="No shared files" description="No files have been shared with this contact yet." />
    return (
      <div className="space-y-2">
        {fileShares.map((share: any) => (
          <div
            key={share.id}
            className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <FolderOpen className="h-4 w-4 text-gray-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-gray-900 dark:text-gray-100 truncate">{share.file_name || share.document_title || `File ${share.file_id?.slice(0, 8)}`}</p>
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
              <th className="text-right py-2.5 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Participants</th>
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
                <td className="py-2.5 px-3 text-right text-gray-600 dark:text-gray-300">{m.participant_count ?? '\u2014'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderActivity = () => {
    if (activityQuery.isLoading) return <LoadingSkeleton />
    if (activities.length === 0) return <EmptyState icon={Activity} title="No activity" description="No activity has been recorded for this contact yet." />
    return (
      <div className="space-y-3">
        {activities.map((a: any) => (
          <div key={a.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
            <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0 mt-0.5">
              <Activity className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{a.title}</p>
                <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
                  {a.activity_type?.replace(/_/g, ' ') || 'note'}
                </span>
              </div>
              {a.description && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{a.description}</p>
              )}
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{formatDate(a.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    )
  }

  const tabContent: Record<TabKey, () => React.ReactNode> = {
    overview: renderOverview,
    invoices: renderInvoices,
    proposals: renderProposals,
    estimates: renderEstimates,
    cashbook: renderCashbook,
    files: renderFiles,
    meetings: renderMeetings,
    activity: renderActivity,
  }

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/contacts')} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <ArrowLeft className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{contact.company_name}</h1>
          {contact.contact_name && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{contact.contact_name}</p>
          )}
        </div>
        {canEdit && !editing && (
          <div className="flex gap-2">
            <button onClick={startEditing} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
              <Pencil className="h-3.5 w-3.5" /> Edit
            </button>
            <button
              onClick={() => { if (confirm('Delete this contact?')) deleteMutation.mutate() }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </button>
          </div>
        )}
        {editing && (
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
              <X className="h-3.5 w-3.5" /> Cancel
            </button>
            <button
              onClick={saveEdit}
              disabled={updateMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" /> Save
            </button>
          </div>
        )}
      </div>

      {/* Details */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field('Company Name', 'company_name')}
          {field('Contact Name', 'contact_name')}
          {field('Type', 'type')}
          {field('Email', 'email', 'email')}
          {field('Phone', 'phone', 'tel')}
          {field('Tax ID', 'tax_id')}
        </div>

        <hr className="my-5 border-gray-100 dark:border-gray-700" />
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Address</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field('Address Line 1', 'address_line1')}
          {field('Address Line 2', 'address_line2')}
          {field('City', 'city')}
          {field('State', 'state')}
          {field('ZIP Code', 'zip_code')}
          {field('Country', 'country')}
        </div>

        <hr className="my-5 border-gray-100 dark:border-gray-700" />
        {field('Notes', 'notes')}
      </div>

      {/* Tabbed Sections */}
      <div className="mt-6">
        {/* Tab bar */}
        <div className="border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
          <nav className="flex gap-0 -mb-px" aria-label="Contact tabs">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                  activeTab === key
                    ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab content */}
        <div className="bg-white dark:bg-gray-900 rounded-b-xl shadow-sm border border-t-0 border-gray-100 dark:border-gray-700 p-5">
          {tabContent[activeTab]()}
        </div>
      </div>
    </div>
  )
}
