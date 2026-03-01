import { useState } from 'react'
import type { Folder } from '@/types/models'

interface FolderTreeProps {
  folders: Folder[]
  selectedFolderId: string | null
  onSelect: (folderId: string | null) => void
}

interface FolderNodeProps {
  folder: Folder
  selectedFolderId: string | null
  onSelect: (folderId: string | null) => void
  depth: number
}

function FolderNode({ folder, selectedFolderId, onSelect, depth }: FolderNodeProps) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = folder.children && folder.children.length > 0
  const isSelected = selectedFolderId === folder.id

  return (
    <div>
      <button
        onClick={() => onSelect(isSelected ? null : folder.id)}
        className={`w-full flex items-center gap-1.5 px-2 py-1 text-sm rounded-md transition-colors ${
          isSelected ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren && (
          <span
            onClick={(e) => {
              e.stopPropagation()
              setExpanded(!expanded)
            }}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 cursor-pointer"
          >
            {expanded ? '\u25BE' : '\u25B8'}
          </span>
        )}
        {!hasChildren && <span className="w-3" />}
        <span>{'\uD83D\uDCC1'}</span>
        <span className="truncate">{folder.name}</span>
      </button>
      {hasChildren && expanded && (
        <div>
          {folder.children!.map((child) => (
            <FolderNode
              key={child.id}
              folder={child}
              selectedFolderId={selectedFolderId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FolderTree({ folders, selectedFolderId, onSelect }: FolderTreeProps) {
  return (
    <div className="space-y-0.5">
      <button
        onClick={() => onSelect(null)}
        className={`w-full flex items-center gap-1.5 px-2 py-1 text-sm rounded-md transition-colors ${
          selectedFolderId === null ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100'
        }`}
      >
        <span>{'\uD83C\uDFE0'}</span>
        <span>All Documents</span>
      </button>
      {folders.map((folder) => (
        <FolderNode
          key={folder.id}
          folder={folder}
          selectedFolderId={selectedFolderId}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  )
}
