import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  starDocument,
  trashDocument,
  restoreDocument,
  getDownloadUrl,
  deleteDocument,
} from '@/api/documents'
import {
  ExternalLink,
  Download,
  Star,
  FolderInput,
  Trash2,
  RotateCcw,
  XCircle,
} from 'lucide-react'

export interface ContextMenuPosition {
  x: number
  y: number
}

export interface ContextMenuItem {
  id: string
  type: 'file' | 'folder'
  name: string
  starred?: boolean
  trashed?: boolean
}

interface FileContextMenuProps {
  position: ContextMenuPosition | null
  item: ContextMenuItem | null
  onClose: () => void
  onOpen: (id: string) => void
  onMove: (id: string, type: 'file' | 'folder') => void
}

export default function FileContextMenu({
  position,
  item,
  onClose,
  onOpen,
  onMove,
}: FileContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['starred'] })
    queryClient.invalidateQueries({ queryKey: ['trashed'] })
    queryClient.invalidateQueries({ queryKey: ['recent'] })
    queryClient.invalidateQueries({ queryKey: ['folders'] })
    queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
  }

  const starMutation = useMutation({
    mutationFn: ({ id, starred }: { id: string; starred: boolean }) => starDocument(id, starred),
    onSuccess: invalidateAll,
  })

  const trashMutation = useMutation({
    mutationFn: (id: string) => trashDocument(id),
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

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (position) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [position, onClose])

  if (!position || !item) return null

  // Adjust position to keep menu on screen
  const menuWidth = 200
  const menuHeight = 250
  const x = Math.min(position.x, window.innerWidth - menuWidth - 8)
  const y = Math.min(position.y, window.innerHeight - menuHeight - 8)

  const menuItems = item.trashed
    ? [
        {
          label: 'Restore',
          icon: RotateCcw,
          onClick: () => {
            restoreMutation.mutate(item.id)
            onClose()
          },
        },
        {
          label: 'Delete permanently',
          icon: XCircle,
          danger: true,
          onClick: () => {
            if (confirm(`Permanently delete "${item.name}"? This cannot be undone.`)) {
              deletePermanentlyMutation.mutate(item.id)
              onClose()
            }
          },
        },
      ]
    : [
        ...(item.type === 'file'
          ? [
              {
                label: 'Open',
                icon: ExternalLink,
                onClick: () => {
                  onOpen(item.id)
                  onClose()
                },
              },
              {
                label: 'Download',
                icon: Download,
                onClick: () => {
                  const a = document.createElement('a')
                  a.href = getDownloadUrl(item.id)
                  a.download = ''
                  a.click()
                  onClose()
                },
              },
            ]
          : [
              {
                label: 'Open folder',
                icon: ExternalLink,
                onClick: () => {
                  onOpen(item.id)
                  onClose()
                },
              },
            ]),
        ...(item.type === 'file'
          ? [
              {
                label: item.starred ? 'Remove star' : 'Add star',
                icon: Star,
                onClick: () => {
                  starMutation.mutate({ id: item.id, starred: !item.starred })
                  onClose()
                },
              },
            ]
          : []),
        {
          label: 'Move to...',
          icon: FolderInput,
          onClick: () => {
            onMove(item.id, item.type)
            onClose()
          },
        },
        ...(item.type === 'file'
          ? [
              {
                label: 'Move to trash',
                icon: Trash2,
                danger: true,
                onClick: () => {
                  trashMutation.mutate(item.id)
                  onClose()
                },
              },
            ]
          : []),
      ]

  return createPortal(
    <div
      ref={ref}
      className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 w-52"
      style={{ left: x, top: y }}
    >
      {menuItems.map((menuItem, i) => {
        const Icon = menuItem.icon
        return (
          <button
            key={i}
            onClick={menuItem.onClick}
            className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
              (menuItem as any).danger
                ? 'text-red-600 hover:bg-red-50'
                : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <Icon className="h-4 w-4" />
            {menuItem.label}
          </button>
        )
      })}
    </div>,
    document.body
  )
}
