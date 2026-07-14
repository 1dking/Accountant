import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Share2, X, Loader2, Search, Check } from 'lucide-react'
import { listContacts, shareFile } from '@/api/contacts'
import { useDebounce } from '@/hooks/useDebounce'
import type { ContactListItem } from '@/types/models'

interface ShareFileDialogProps {
  isOpen: boolean
  fileId: string | null
  fileName: string
  onClose: () => void
}

type Permission = 'view' | 'download'

/**
 * Share a Drive file with a contact, which surfaces it in their client portal.
 *
 * This is the sharing mechanism the backend actually has (FileShare →
 * contact). Public share tokens only cover invoices/estimates/proposals, not
 * documents — so there is no "anyone with the link" option to offer here.
 */
export default function ShareFileDialog({
  isOpen,
  fileId,
  fileName,
  onClose,
}: ShareFileDialogProps) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<ContactListItem | null>(null)
  const [permission, setPermission] = useState<Permission>('view')

  const debouncedSearch = useDebounce(search, 300)

  const { data: contacts, isLoading } = useQuery({
    queryKey: ['contacts', 'share-picker', debouncedSearch],
    queryFn: () =>
      listContacts({ search: debouncedSearch || undefined, page_size: 8, is_active: true }),
    enabled: isOpen,
  })

  const shareMutation = useMutation({
    mutationFn: () =>
      shareFile({
        file_id: fileId!,
        contact_id: selected!.id,
        permission,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      toast.success(
        `Shared "${fileName}" with ${selected!.contact_name || selected!.company_name}`,
      )
      handleClose()
    },
    onError: (err) => {
      toast.error(
        `Couldn't share the file: ${err instanceof Error ? err.message : 'Unknown error'}`,
      )
    },
  })

  const handleClose = () => {
    setSearch('')
    setSelected(null)
    setPermission('view')
    shareMutation.reset()
    onClose()
  }

  if (!isOpen || !fileId) return null

  const results = contacts?.data ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Share2 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Share file
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 rounded"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Give a contact access to <span className="font-medium">{fileName}</span> in
            their client portal.
          </p>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              autoFocus
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setSelected(null)
              }}
              placeholder="Search contacts..."
              className="w-full pl-9 pr-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
          </div>

          <div className="max-h-52 overflow-y-auto border rounded-md dark:border-gray-700">
            {isLoading && (
              <div className="flex items-center gap-2 px-3 py-4 text-sm text-gray-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </div>
            )}

            {!isLoading && results.length === 0 && (
              <p className="px-3 py-4 text-sm text-gray-500">
                No contacts match "{search}".
              </p>
            )}

            {results.map((contact) => {
              const isSelected = selected?.id === contact.id
              return (
                <button
                  key={contact.id}
                  onClick={() => setSelected(contact)}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-800 ${
                    isSelected ? 'bg-blue-50 dark:bg-blue-900/30' : ''
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {contact.contact_name || contact.company_name}
                    </p>
                    {contact.email && (
                      <p className="text-xs text-gray-500 truncate">{contact.email}</p>
                    )}
                  </div>
                  {isSelected && (
                    <Check className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
                  )}
                </button>
              )
            })}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Permission
            </label>
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value as Permission)}
              className="w-full px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              <option value="view">View only</option>
              <option value="download">View &amp; download</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md"
          >
            Cancel
          </button>
          <button
            onClick={() => shareMutation.mutate()}
            disabled={!selected || shareMutation.isPending}
            className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {shareMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Share
          </button>
        </div>
      </div>
    </div>
  )
}
