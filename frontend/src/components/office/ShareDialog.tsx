import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { shareOfficeDoc, getOfficeCollaborators } from '@/api/office'
import { X, UserPlus, Users } from 'lucide-react'
import { getInitials } from '@/lib/utils'
import type { OfficePermission } from '@/types/models'

interface ShareDialogProps {
  docId: string
  isOpen: boolean
  onClose: () => void
}

export default function ShareDialog({ docId, isOpen, onClose }: ShareDialogProps) {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [permission, setPermission] = useState<OfficePermission>('edit')

  const { data: collabData } = useQuery({
    queryKey: ['office-collaborators', docId],
    queryFn: () => getOfficeCollaborators(docId),
    enabled: isOpen,
  })

  const collaborators = collabData?.data ?? []

  const shareMutation = useMutation({
    mutationFn: () => shareOfficeDoc(docId, { user_id: email, permission }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-collaborators', docId] })
      setEmail('')
    },
    onError: (err: Error) => {
      alert(`Failed to share: ${err.message}`)
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
            <input
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter user email or ID..."
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value as OfficePermission)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
            >
              <option value="view">View</option>
              <option value="comment">Comment</option>
              <option value="edit">Edit</option>
            </select>
            <button
              onClick={() => shareMutation.mutate()}
              disabled={!email.trim() || shareMutation.isPending}
              className="px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <UserPlus className="h-4 w-4" />
            </button>
          </div>

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
