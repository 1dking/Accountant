import { useNavigate } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { starOfficeDoc, trashOfficeDoc } from '@/api/office'
import { Star, Trash2, FileText, Table2, Presentation, BookOpen } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import type { OfficeDocListItem, DocType } from '@/types/models'

interface OfficeDocCardProps {
  document: OfficeDocListItem
}

const DOC_CONFIG: Record<DocType, { icon: typeof FileText; color: string; bgColor: string; route: string }> = {
  document: { icon: FileText, color: 'text-blue-600', bgColor: 'bg-blue-50', route: '/docs' },
  spreadsheet: { icon: Table2, color: 'text-green-600', bgColor: 'bg-green-50', route: '/sheets' },
  presentation: { icon: Presentation, color: 'text-orange-600', bgColor: 'bg-orange-50', route: '/slides' },
}

export default function OfficeDocCard({ document: doc }: OfficeDocCardProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const config = DOC_CONFIG[doc.doc_type]
  const Icon = config.icon

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(doc.id, !doc.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-docs'] })
    },
  })

  const trashMutation = useMutation({
    mutationFn: () => trashOfficeDoc(doc.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-docs'] })
    },
  })

  return (
    <div
      className="group bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => navigate(`${config.route}/${doc.id}`)}
    >
      {/* Colored thumbnail area */}
      <div className={`h-32 ${config.bgColor} flex items-center justify-center relative`}>
        <Icon className={`h-12 w-12 ${config.color} opacity-40`} />
        {/* Hover actions */}
        <div
          className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => e.stopPropagation()}
        >
          {doc.doc_type === 'document' && (
            <button
              onClick={() => navigate(`${config.route}/${doc.id}/read`)}
              className="p-1.5 rounded-full bg-white/90 hover:bg-white dark:bg-gray-900 shadow-sm text-gray-400 dark:text-gray-500 hover:text-blue-600 transition-colors"
              title="Read view"
            >
              <BookOpen className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => starMutation.mutate()}
            className={`p-1.5 rounded-full bg-white/90 hover:bg-white dark:bg-gray-900 shadow-sm transition-colors ${
              doc.is_starred ? 'text-yellow-500' : 'text-gray-400 dark:text-gray-500 hover:text-yellow-500'
            }`}
            title={doc.is_starred ? 'Remove star' : 'Add star'}
          >
            <Star className="h-4 w-4" fill={doc.is_starred ? 'currentColor' : 'none'} />
          </button>
          <button
            onClick={() => {
              if (confirm(`Move "${doc.title}" to trash?`)) {
                trashMutation.mutate()
              }
            }}
            className="p-1.5 rounded-full bg-white/90 hover:bg-white dark:bg-gray-900 shadow-sm text-gray-400 dark:text-gray-500 hover:text-red-500 transition-colors"
            title="Move to trash"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
        {/* Star indicator when starred */}
        {doc.is_starred && (
          <div className="absolute top-2 left-2">
            <Star className="h-4 w-4 text-yellow-500" fill="currentColor" />
          </div>
        )}
      </div>
      {/* Info */}
      <div className="p-3">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{doc.title}</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {doc.last_accessed_at
            ? `Opened ${formatRelativeTime(doc.last_accessed_at)}`
            : `Modified ${formatRelativeTime(doc.updated_at)}`}
        </p>
      </div>
    </div>
  )
}
