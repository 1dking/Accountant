import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { shareOfficeDoc, unshareOfficeDoc, getOfficeCollaborators } from '@/api/office'
import { listUsers } from '@/api/auth'
import { X, UserPlus, Users, Trash2, ChevronDown } from 'lucide-react'
import { getInitials } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import type { OfficePermission } from '@/types/models'

interface ShareDialogProps {
  docId: string
  isOpen: boolean
  onClose: () => void
}

export default function ShareDialog({ docId, isOpen, onClose }: ShareDialogProps) {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [permission, setPermission] = useState<OfficePermission>('edit')

  const { data: collabData } = useQuery({
    queryKey: ['office-collaborators', docId],
    queryFn: () => getOfficeCollaborators(docId),
    enabled: isOpen,
  })

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers(),
    enabled: isOpen,
  })

  const collaborators = collabData?.data ?? []
  const allUsers = usersData?.data ?? []

  // Filter out current user and already-shared users
  const collabUserIds = new Set(collaborators.map((c) => c.user_id))
  const availableUsers = allUsers.filter(
    (u) => u.id !== currentUser?.id && !collabUserIds.has(u.id) && u.is_active
  )

  const shareMutation = useMutation({
    mutationFn: () => shareOfficeDoc(docId, { user_id: selectedUserId, permission }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-collaborators', docId] })
      setSelectedUserId('')
    },
    onError: (err: Error) => {
      alert(`Failed to share: ${err.message}`)
    },
  })

  const unshareMutation = useMutation({
    mutationFn: (userId: string) => unshareOfficeDoc(docId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-collaborators', docId] })
    },
    onError: (err: Error) => {
      alert(`Failed to remove access: ${err.message}`)
    },
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Share document</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Add people */}
        <div className="px-5 py-4 space-y-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none pr-8"
              >
                <option value="">Select a team member...</option>
                {availableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            </div>
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value as OfficePermission)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
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

          {availableUsers.length === 0 && allUsers.length > 0 && (
            <p className="text-xs text-gray-500">All team members already have access.</p>
          )}

          {/* Current collaborators */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Users className="h-4 w-4 text-gray-500" />
              <h3 className="text-sm font-medium text-gray-700">People with access</h3>
            </div>
            {collaborators.length === 0 ? (
              <p className="text-sm text-gray-500 py-2">Only you have access</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {collaborators.map((collab) => (
                  <div key={collab.id} className="flex items-center gap-3 py-2">
                    <div className="h-8 w-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-medium shrink-0">
                      {getInitials(collab.user_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{collab.user_name}</p>
                      <p className="text-xs text-gray-500 truncate">{collab.user_email}</p>
                    </div>
                    <span className="text-xs text-gray-500 capitalize px-2 py-0.5 bg-gray-100 rounded-full">
                      {collab.permission}
                    </span>
                    <button
                      onClick={() => unshareMutation.mutate(collab.user_id)}
                      disabled={unshareMutation.isPending}
                      className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md"
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

        {/* Footer */}
        <div className="px-5 py-3 border-t bg-gray-50 rounded-b-lg flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
