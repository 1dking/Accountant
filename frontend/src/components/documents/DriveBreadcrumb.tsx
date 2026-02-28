import { ChevronRight } from 'lucide-react'
import type { Folder } from '@/types/models'

interface DriveBreadcrumbProps {
  currentFolderId: string | null
  folders: Folder[]
  onNavigate: (folderId: string | null) => void
}

function buildBreadcrumbPath(folderId: string | null, folders: Folder[]): { id: string | null; name: string }[] {
  if (!folderId) return []

  // Flatten all folders into a map for easy lookup
  const folderMap = new Map<string, { name: string; parent_id: string | null }>()
  function flatten(items: Folder[]) {
    for (const f of items) {
      folderMap.set(f.id, { name: f.name, parent_id: f.parent_id })
      if (f.children) flatten(f.children)
    }
  }
  flatten(folders)

  // Walk up the parent chain
  const path: { id: string | null; name: string }[] = []
  let current: string | null = folderId
  while (current) {
    const folder = folderMap.get(current)
    if (!folder) break
    path.unshift({ id: current, name: folder.name })
    current = folder.parent_id
  }

  return path
}

export default function DriveBreadcrumb({ currentFolderId, folders, onNavigate }: DriveBreadcrumbProps) {
  const path = buildBreadcrumbPath(currentFolderId, folders)

  return (
    <nav className="flex items-center gap-1 text-sm min-w-0">
      <button
        onClick={() => onNavigate(null)}
        className={`shrink-0 px-1.5 py-0.5 rounded hover:bg-gray-100 transition-colors ${
          !currentFolderId ? 'font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'
        }`}
      >
        My Drive
      </button>
      {path.map((segment) => (
        <span key={segment.id} className="flex items-center gap-1 min-w-0">
          <ChevronRight className="h-3.5 w-3.5 text-gray-400 shrink-0" />
          <button
            onClick={() => onNavigate(segment.id)}
            className={`truncate px-1.5 py-0.5 rounded hover:bg-gray-100 transition-colors max-w-40 ${
              segment.id === currentFolderId ? 'font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {segment.name}
          </button>
        </span>
      ))}
    </nav>
  )
}
