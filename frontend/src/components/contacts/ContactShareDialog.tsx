import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { X, UserPlus, Users, Trash2, ChevronDown } from 'lucide-react'
import {
  shareContact,
  unshareContact,
  getContactCollaborators,
} from '@/api/contacts'
import { listUsers } from '@/api/auth'
import { getInitials } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

interface Props {
  contactId: string
  contactName: string
  isOpen: boolean
  onClose: () => void
}

/**
 * Share one contact with a colleague. Mirrors the Office ShareDialog — the app's
 * existing user-to-user grant UI — against the contact endpoints.
 *
 * Sharing hands over the whole file: the colleague also sees this contact's
 * invoices, proposals, tasks and calls. Only the owner (or an admin) sees this
 * dialog's actions succeed; the backend enforces it.
 */
export default function ContactShareDialog({ contactId, contactName, isOpen, onClose }: Props) {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [permission, setPermission] = useState<'view' | 'edit'>('view')

  const { data: collabData } = useQuery({
    queryKey: ['contact-collaborators', contactId],
    queryFn: () => getContactCollaborators(contactId),
    enabled: isOpen,
  })

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
    enabled: isOpen,
  })

  const collaborators = collabData?.data ?? []
  const allUsers = usersData?.data ?? []

  const collabUserIds = new Set(collaborators.map((c) => c.user_id))
  // A client can't be shared with — the backend refuses it — but the users list
  // here is staff only, so no need to filter by role. Just exclude myself and
  // anyone already on the file.
  const availableUsers = allUsers.filter(
    (u) => u.id !== currentUser?.id && !collabUserIds.has(u.id) && u.is_active,
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['contact-collaborators', contactId] })

  const shareMutation = useMutation({
    mutationFn: () => shareContact(contactId, { user_id: selectedUserId, permission }),
    onSuccess: () => {
      invalidate()
      setSelectedUserId('')
      toast.success('Contact shared')
    },
    onError: (err: unknown) =>
      toast.error((err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message || 'Failed to share'),
  })

  const unshareMutation = useMutation({
    mutationFn: (userId: string) => unshareContact(contactId, userId),
    onSuccess: () => {
      invalidate()
      toast.success('Access revoked')
    },
    onError: (err: unknown) =>
      toast.error((err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message || 'Failed to revoke'),
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Share contact</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{contactName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            The person you share with also sees this contact&apos;s invoices,
            proposals, tasks and call history.
          </p>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none pr-8"
              >
                <option value="">Select a colleague...</option>
                {availableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500 pointer-events-none" />
            </div>
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value as 'view' | 'edit')}
              className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900"
            >
              <option value="view">View</option>
              <option value="edit">Edit</option>
            </select>
            <button
              onClick={() => shareMutation.mutate()}
              disabled={!selectedUserId || shareMutation.isPending}
              className="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <UserPlus className="h-4 w-4" />
            </button>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Users className="h-4 w-4 text-gray-500 dark:text-gray-400" />
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">People with access</h3>
            </div>
            {collaborators.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-2">Not shared with anyone yet</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {collaborators.map((collab) => (
                  <div key={collab.id} className="flex items-center gap-3 py-2">
                    <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xs font-medium shrink-0">
                      {getInitials(collab.user_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{collab.user_name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{collab.user_email}</p>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400 capitalize px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded-full">
                      {collab.permission}
                    </span>
                    <button
                      onClick={() => unshareMutation.mutate(collab.user_id)}
                      disabled={unshareMutation.isPending}
                      className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-md"
                      title="Remove access"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="px-5 py-3 border-t bg-gray-50 dark:bg-gray-950 rounded-b-lg flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
