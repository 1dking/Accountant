import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  starDocument,
  starFolder,
  trashDocument,
  restoreDocument,
  deleteDocumentPermanent,
  deleteFolderRecursive,
  getDownloadUrl,
} from '@/api/documents'
import {
  ExternalLink,
  Download,
  Star,
  FolderInput,
  Trash2,
  RotateCcw,
  XCircle,
  Pencil,
  Share2,
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
  onRename?: (id: string, type: 'file' | 'folder', currentName: string) => void
}

export default function FileContextMenu({
  position,
  item,
  onClose,
  onOpen,
  onMove,
  onRename,
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
    mutationFn: async ({ id, type, starred }: { id: string; type: string; starred: boolean }) => {
      if (type === 'folder') await starFolder(id, starred)
      else await starDocument(id, starred)
    },
    onSuccess: () => {
      invalidateAll()
      toast.success('Updated')
    },
  })

  const trashMutation = useMutation({
    mutationFn: (id: string) => trashDocument(id),
    onSuccess: () => {
      invalidateAll()
      toast.success('Moved to trash')
    },
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => restoreDocument(id),
    onSuccess: () => {
      invalidateAll()
      toast.success('Restored')
    },
  })

  const deleteDocMutation = useMutation({
    mutationFn: (id: string) => deleteDocumentPermanent(id),
    onSuccess: () => {
      invalidateAll()
      toast.success('Permanently deleted')
    },
    onError: (err: Error) => toast.error(err.message || 'Delete failed'),
  })

  const deleteFolderMutation = useMutation({
    mutationFn: (id: string) => deleteFolderRecursive(id),
    onSuccess: () => {
      invalidateAll()
      toast.success('Folder and contents deleted')
    },
    onError: (err: Error) => toast.error(err.message || 'Delete failed'),
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

  const menuWidth = 220
  const menuHeight = 320
  const x = Math.min(position.x, window.innerWidth - menuWidth - 8)
  const y = Math.min(position.y, window.innerHeight - menuHeight - 8)

  type MenuItem = {
    label: string
    icon: React.ComponentType<{ className?: string }>
    onClick: () => void
    danger?: boolean
    divider?: boolean
  }

  const menuItems: MenuItem[] = item.trashed
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
              if (item.type === 'folder') {
                deleteFolderMutation.mutate(item.id)
              } else {
                deleteDocMutation.mutate(item.id)
              }
              onClose()
            }
          },
        },
      ]
    : [
        // Open
        {
          label: item.type === 'folder' ? 'Open' : 'Open',
          icon: ExternalLink,
          onClick: () => {
            onOpen(item.id)
            onClose()
          },
        },
        // Download (files only)
        ...(item.type === 'file'
          ? [
              {
                label: 'Download',
                icon: Download,
                onClick: () => {
                  const a = document.createElement('a')
                  a.href = getDownloadUrl(item.id)
                  a.download = item.name
                  a.click()
                  onClose()
                },
              },
            ]
          : []),
        // Rename
        {
          label: 'Rename',
          icon: Pencil,
          divider: true,
          onClick: () => {
            onRename?.(item.id, item.type, item.name)
            onClose()
          },
        },
        // Star
        {
          label: item.starred ? 'Remove star' : 'Add star',
          icon: Star,
          onClick: () => {
            starMutation.mutate({ id: item.id, type: item.type, starred: !item.starred })
            onClose()
          },
        },
        // Move
        {
          label: 'Move to...',
          icon: FolderInput,
          onClick: () => {
            onMove(item.id, item.type)
            onClose()
          },
        },
        // Share (placeholder)
        {
          label: 'Share',
          icon: Share2,
          divider: true,
          onClick: () => {
            toast.info('Share link copied (coming soon)')
            onClose()
          },
        },
        // Delete
        {
          label: item.type === 'folder' ? 'Delete folder' : 'Move to trash',
          icon: Trash2,
          danger: true,
          onClick: () => {
            if (item.type === 'folder') {
              if (confirm(`Delete "${item.name}" and all its contents? This cannot be undone.`)) {
                deleteFolderMutation.mutate(item.id)
                onClose()
              }
            } else {
              trashMutation.mutate(item.id)
              onClose()
            }
          },
        },
      ]

  return createPortal(
    <div
      ref={ref}
      className="fixed z-[100] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl py-1 w-56 animate-in fade-in zoom-in-95 duration-100"
      style={{ left: x, top: y }}
    >
      {menuItems.map((menuItem, i) => {
        const Icon = menuItem.icon
        return (
          <div key={i}>
            {menuItem.divider && i > 0 && (
              <div className="h-px bg-gray-100 dark:bg-gray-800 my-1" />
            )}
            <button
              onClick={menuItem.onClick}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors ${
                menuItem.danger
                  ? 'text-red-600 hover:bg-red-50 dark:hover:bg-red-950'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {menuItem.label}
            </button>
          </div>
        )
      })}
    </div>,
    document.body,
  )
}
