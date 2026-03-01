import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listTrashed, emptyTrash, restoreDocument, deleteDocument } from '@/api/documents'
import { formatFileSize, formatRelativeTime } from '@/lib/utils'
import { Trash2, RotateCcw, XCircle, AlertTriangle, File, FileText, Image } from 'lucide-react'

function getIcon(mimeType?: string) {
  if (!mimeType) return File
  if (mimeType.startsWith('image/')) return Image
  if (mimeType === 'application/pdf') return FileText
  return File
}

export default function TrashView() {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['trashed'],
    queryFn: listTrashed,
  })

  const items = data?.data ?? []

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['trashed'] })
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
    queryClient.invalidateQueries({ queryKey: ['folders'] })
  }

  const emptyTrashMutation = useMutation({
    mutationFn: emptyTrash,
    onSuccess: invalidateAll,
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => restoreDocument(id),
    onSuccess: invalidateAll,
  })

  const deletePermanentlyMutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: invalidateAll,
  })

  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-14 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-10 w-10 text-red-400 mx-auto mb-3" />
        <p className="text-red-600 font-medium">Failed to load trash</p>
      </div>
    )
  }

  return (
    <div>
      {/* Trash header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Trash2 className="h-5 w-5 text-gray-400 dark:text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Trash</h2>
          <span className="text-sm text-gray-500 dark:text-gray-400">({items.length} items)</span>
        </div>
        {items.length > 0 && (
          <button
            onClick={() => {
              if (confirm('Permanently delete all items in trash? This cannot be undone.')) {
                emptyTrashMutation.mutate()
              }
            }}
            disabled={emptyTrashMutation.isPending}
            className="px-3 py-1.5 text-sm font-medium text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {emptyTrashMutation.isPending ? 'Emptying...' : 'Empty Trash'}
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="text-center py-16">
          <Trash2 className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-gray-500 dark:text-gray-400 font-medium">Trash is empty</h3>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Items moved to trash will appear here</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {items.map((item: any) => {
            const Icon = getIcon(item.mime_type)
            return (
              <div
                key={item.id}
                className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <Icon className="h-5 w-5 text-gray-400 dark:text-gray-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {item.title || item.original_filename || item.filename}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {formatFileSize(item.file_size ?? 0)}
                    {' \u00B7 '}
                    {formatRelativeTime(item.updated_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => restoreMutation.mutate(item.id)}
                    disabled={restoreMutation.isPending}
                    title="Restore"
                    className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors disabled:opacity-50"
                  >
                    <RotateCcw className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Permanently delete "${item.title || item.original_filename}"? This cannot be undone.`)) {
                        deletePermanentlyMutation.mutate(item.id)
                      }
                    }}
                    disabled={deletePermanentlyMutation.isPending}
                    title="Delete permanently"
                    className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
