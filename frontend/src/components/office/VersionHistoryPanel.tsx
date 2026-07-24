import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listOfficeVersions, createOfficeVersion, restoreOfficeVersion } from '@/api/office'
import { History, RotateCcw, Save } from 'lucide-react'
import { getInitials } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

interface VersionHistoryPanelProps {
  docId: string
  onRestored: (contentJson: Record<string, unknown>) => void
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function VersionHistoryPanel({ docId, onRestored }: VersionHistoryPanelProps) {
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)

  const { data } = useQuery({
    queryKey: ['office-versions', docId],
    queryFn: () => listOfficeVersions(docId),
  })

  const versions = data?.data ?? []

  const saveMutation = useMutation({
    mutationFn: () => createOfficeVersion(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['office-versions', docId] }),
    onError: (err: Error) => alert(`Failed to save version: ${err.message}`),
  })

  const restoreMutation = useMutation({
    mutationFn: (versionId: string) => restoreOfficeVersion(docId, versionId),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['office-versions', docId] })
      queryClient.invalidateQueries({ queryKey: ['office-doc', docId] })
      if (res.data.content_json) {
        onRestored(res.data.content_json as Record<string, unknown>)
      }
    },
    onError: (err: Error) => alert(`Failed to restore version: ${err.message}`),
  })

  return (
    <div className="w-72 shrink-0 bg-white dark:bg-gray-900 border-l dark:border-gray-700 flex flex-col overflow-hidden">
      <div className="px-3 py-2 border-b dark:border-gray-700 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-gray-500 dark:text-gray-400" />
          <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wide">
            Version History
          </span>
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="p-1 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50"
          title="Save current version"
        >
          <Save className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {versions.length === 0 ? (
          <p className="px-3 py-4 text-xs text-gray-400 dark:text-gray-500 italic">
            No saved versions yet. Versions are captured automatically as you edit, or click Save above.
          </p>
        ) : (
          versions.map((v, idx) => (
            <div
              key={v.id}
              className="px-3 py-2 border-b dark:border-gray-800 flex items-start gap-2 hover:bg-gray-50 dark:hover:bg-gray-800/50"
            >
              <div className="h-6 w-6 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 flex items-center justify-center text-[10px] font-medium shrink-0 mt-0.5">
                {v.created_by === currentUser?.id ? getInitials(currentUser?.full_name || '') : '?'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  Version {v.version_number}
                  {idx === 0 && (
                    <span className="ml-1.5 text-[10px] font-normal text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded-full">
                      Latest
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-gray-400 dark:text-gray-500">{formatWhen(v.created_at)}</p>
              </div>
              <button
                onClick={() => confirm(`Restore version ${v.version_number}? Your current content will be saved as a new version first.`) && restoreMutation.mutate(v.id)}
                disabled={restoreMutation.isPending}
                className="p-1 text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50 shrink-0"
                title="Restore this version"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
