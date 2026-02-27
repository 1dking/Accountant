import { useNavigate } from 'react-router'
import type { DocumentListItem } from '@/types/models'
import { formatFileSize, formatDate } from '@/lib/utils'
import { DOCUMENT_STATUSES } from '@/lib/constants'

interface DocumentCardProps {
  document: DocumentListItem
  selected?: boolean
  onSelect?: (id: string) => void
}

const FILE_ICONS: Record<string, string> = {
  'application/pdf': '\uD83D\uDCC4',
  'image/': '\uD83D\uDDBC',
  'application/vnd.': '\uD83D\uDCCA',
  'text/': '\uD83D\uDCDD',
  default: '\uD83D\uDCC1',
}

function getFileIcon(mimeType: string): string {
  for (const [key, icon] of Object.entries(FILE_ICONS)) {
    if (key !== 'default' && mimeType.startsWith(key)) return icon
  }
  return FILE_ICONS.default
}

export default function DocumentCard({ document: doc, selected, onSelect }: DocumentCardProps) {
  const navigate = useNavigate()
  const statusInfo = DOCUMENT_STATUSES.find((s) => s.value === doc.status)

  return (
    <div
      className={`group bg-white border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer ${
        selected ? 'ring-2 ring-blue-500' : ''
      }`}
      onClick={() => navigate(`/documents/${doc.id}`)}
    >
      <div className="flex items-start gap-3">
        {onSelect && (
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => {
              e.stopPropagation()
              onSelect(doc.id)
            }}
            onClick={(e) => e.stopPropagation()}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600"
          />
        )}
        <div className="text-2xl">{getFileIcon(doc.mime_type)}</div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">
            {doc.title || doc.original_filename}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <span>{formatFileSize(doc.file_size)}</span>
            <span>{'\u00B7'}</span>
            <span>{formatDate(doc.created_at)}</span>
            <span>{'\u00B7'}</span>
            <span className="capitalize">{doc.document_type.replace('_', ' ')}</span>
          </div>
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {statusInfo && (
              <span className={`px-2 py-0.5 text-xs rounded-full ${statusInfo.color}`}>
                {statusInfo.label}
              </span>
            )}
            {doc.tags.map((tag) => (
              <span
                key={tag.id}
                className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600"
                style={tag.color ? { backgroundColor: tag.color + '20', color: tag.color } : undefined}
              >
                {tag.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
