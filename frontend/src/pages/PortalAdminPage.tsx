import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  UserCog,
  Plus,
  Mail,
  RefreshCw,
  Search,
  CheckCircle,
  Clock,
  XCircle,
  Send,
} from 'lucide-react'
import { listContacts } from '@/api/contacts'
import { createInvitation, listInvitations, resendInvitation } from '@/api/contacts'
import type { ContactListItem } from '@/types/models'

interface Invitation {
  id: string
  contact_id: string
  email: string
  status: string
  created_at: string
  accepted_at: string | null
  contact?: { company_name: string; contact_name: string | null }
}

export default function PortalAdminPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteContactId, setInviteContactId] = useState('')

  const { data: invitationsData, isLoading: loadingInvitations } = useQuery({
    queryKey: ['portal-invitations'],
    queryFn: () => listInvitations() as Promise<{ data: Invitation[] }>,
  })

  const { data: contactsData } = useQuery({
    queryKey: ['contacts', { page_size: 200, type: 'client' }],
    queryFn: () => listContacts({ page_size: 200, type: 'client' }),
  })

  const inviteMutation = useMutation({
    mutationFn: (data: { contact_id: string; email: string }) => createInvitation({ email: data.email, role: 'client', contact_id: data.contact_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-invitations'] })
      toast.success('Invitation sent')
      setShowInviteModal(false)
      setInviteEmail('')
      setInviteContactId('')
    },
    onError: () => toast.error('Failed to send invitation'),
  })

  const resendMutation = useMutation({
    mutationFn: (invitationId: string) => resendInvitation(invitationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-invitations'] })
      toast.success('Invitation resent')
    },
    onError: () => toast.error('Failed to resend invitation'),
  })

  const invitations: Invitation[] = (invitationsData as any)?.data ?? []
  const contacts: ContactListItem[] = contactsData?.data ?? []

  const filtered = invitations.filter((inv) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      inv.email.toLowerCase().includes(q) ||
      inv.contact?.company_name?.toLowerCase().includes(q) ||
      inv.contact?.contact_name?.toLowerCase().includes(q)
    )
  })

  const statusIcon = (status: string) => {
    switch (status) {
      case 'accepted':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'pending':
        return <Clock className="h-4 w-4 text-amber-500" />
      case 'expired':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      accepted: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
      expired: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    }
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-600'}`}>
        {statusIcon(status)}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  const acceptedCount = invitations.filter((i) => i.status === 'accepted').length
  const pendingCount = invitations.filter((i) => i.status === 'pending').length

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <UserCog className="h-6 w-6" />
            Portal Administration
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Manage client portal accounts and invitations</p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
        >
          <Plus className="h-4 w-4" />
          Invite Client
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Invitations</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{invitations.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Active Portal Users</p>
          <p className="text-2xl font-bold text-green-600">{acceptedCount}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Pending Invitations</p>
          <p className="text-2xl font-bold text-amber-600">{pendingCount}</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm"
          placeholder="Search invitations..."
        />
      </div>

      {/* Invitations table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 overflow-hidden">
        {loadingInvitations ? (
          <div className="p-8 text-center text-gray-400">Loading invitations...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            {invitations.length === 0 ? 'No invitations yet. Invite your first client!' : 'No results found.'}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Client</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Email</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Sent</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
              {filtered.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/50">
                  <td className="px-4 py-3 text-gray-900 dark:text-gray-100">
                    {inv.contact?.company_name || inv.contact?.contact_name || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{inv.email}</td>
                  <td className="px-4 py-3">{statusBadge(inv.status)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {new Date(inv.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {inv.status === 'pending' && (
                      <button
                        onClick={() => resendMutation.mutate(inv.id)}
                        disabled={resendMutation.isPending}
                        className="text-blue-600 dark:text-blue-400 hover:underline text-xs flex items-center gap-1 ml-auto"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Resend
                      </button>
                    )}
                    {inv.status === 'accepted' && (
                      <span className="text-xs text-green-600 dark:text-green-400">Active</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
              <Send className="h-5 w-5" />
              Invite Client to Portal
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Contact</label>
                <select
                  value={inviteContactId}
                  onChange={(e) => {
                    setInviteContactId(e.target.value)
                    const c = contacts.find((c) => c.id === e.target.value)
                    if (c?.email) setInviteEmail(c.email)
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Select a contact...</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.company_name}{c.contact_name ? ` (${c.contact_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Address</label>
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-gray-400" />
                  <input
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                    placeholder="client@example.com"
                    type="email"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowInviteModal(false)
                  setInviteEmail('')
                  setInviteContactId('')
                }}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (!inviteContactId || !inviteEmail) {
                    toast.error('Select a contact and enter an email')
                    return
                  }
                  inviteMutation.mutate({ contact_id: inviteContactId, email: inviteEmail })
                }}
                disabled={inviteMutation.isPending || !inviteContactId || !inviteEmail}
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
              >
                <Send className="h-4 w-4" />
                {inviteMutation.isPending ? 'Sending...' : 'Send Invitation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
