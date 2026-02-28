import { useDraggable, useDroppable } from '@dnd-kit/core'
import { Folder as FolderIcon, FileText, Image, FileSpreadsheet, File, Star } from 'lucide-react'
import { formatFileSize, formatRelativeTime } from '@/lib/utils'
import type { Folder } from '@/types/models'
import type { ContextMenuItem } from './FileContextMenu'

// A union type for items displayed in the grid/list
export interface DriveItem {
  id: string
  type: 'file' | 'folder'
  name: string
  mime_type?: string
  file_size?: number
  updated_at: string
  starred?: boolean
  folder_id?: string | null
}

interface DriveGridViewProps {
  items: DriveItem[]
  viewMode: 'grid' | 'list'
  onItemClick: (item: DriveItem) => void
  onContextMenu: (e: React.MouseEvent, item: ContextMenuItem) => void
}

function getFileIcon(mimeType?: string) {
  if (!mimeType) return File
  if (mimeType === 'folder') return FolderIcon
  if (mimeType.startsWith('image/')) return Image
  if (mimeType === 'application/pdf') return FileText
  if (
    mimeType.includes('spreadsheet') ||
    mimeType.includes('excel') ||
    mimeType === 'text/csv'
  )
    return FileSpreadsheet
  return File
}

function getFileIconColor(mimeType?: string) {
  if (!mimeType) return 'text-gray-400'
  if (mimeType === 'folder') return 'text-blue-500'
  if (mimeType.startsWith('image/')) return 'text-green-500'
  if (mimeType === 'application/pdf') return 'text-red-500'
  if (
    mimeType.includes('spreadsheet') ||
    mimeType.includes('excel') ||
    mimeType === 'text/csv'
  )
    return 'text-emerald-600'
  return 'text-gray-400'
}

// Draggable wrapper for items
function DraggableItem({
  item,
  children,
}: {
  item: DriveItem
  children: React.ReactNode
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `drag-${item.type}-${item.id}`,
    data: { item },
  })

  const style = transform
    ? {
        transform: `translate(${transform.x}px, ${transform.y}px)`,
        zIndex: 50,
        opacity: 0.8,
      }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={isDragging ? 'pointer-events-none' : ''}
    >
      {children}
    </div>
  )
}

// Droppable folder wrapper
function DroppableFolder({
  folderId,
  children,
}: {
  folderId: string
  children: React.ReactNode
}) {
  const { isOver, setNodeRef } = useDroppable({
    id: `drop-folder-${folderId}`,
    data: { folderId },
  })

  return (
    <div
      ref={setNodeRef}
      className={`transition-colors rounded-lg ${isOver ? 'ring-2 ring-blue-400 bg-blue-50' : ''}`}
    >
      {children}
    </div>
  )
}

// Grid card for a single item
function GridCard({
  item,
  onItemClick,
  onContextMenu,
}: {
  item: DriveItem
  onItemClick: (item: DriveItem) => void
  onContextMenu: (e: React.MouseEvent, item: ContextMenuItem) => void
}) {
  const Icon = getFileIcon(item.type === 'folder' ? 'folder' : item.mime_type)
  const iconColor = getFileIconColor(item.type === 'folder' ? 'folder' : item.mime_type)

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    onContextMenu(e, {
      id: item.id,
      type: item.type,
      name: item.name,
      starred: item.starred,
    })
  }

  const card = (
    <div
      onClick={() => onItemClick(item)}
      onContextMenu={handleContextMenu}
      className="group bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md hover:border-gray-300 transition-all cursor-pointer select-none"
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg bg-gray-50 ${iconColor}`}>
          <Icon className="h-8 w-8" />
        </div>
        {item.starred && (
          <Star className="h-4 w-4 text-yellow-400 fill-yellow-400" />
        )}
      </div>
      <p className="text-sm font-medium text-gray-900 truncate" title={item.name}>
        {item.name}
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {item.type === 'folder' ? 'Folder' : formatFileSize(item.file_size ?? 0)}
        {' \u00B7 '}
        {formatRelativeTime(item.updated_at)}
      </p>
    </div>
  )

  const draggableCard = (
    <DraggableItem item={item}>
      {card}
    </DraggableItem>
  )

  if (item.type === 'folder') {
    return (
      <DroppableFolder folderId={item.id}>
        {draggableCard}
      </DroppableFolder>
    )
  }

  return draggableCard
}

// List row for a single item
function ListRow({
  item,
  onItemClick,
  onContextMenu,
}: {
  item: DriveItem
  onItemClick: (item: DriveItem) => void
  onContextMenu: (e: React.MouseEvent, item: ContextMenuItem) => void
}) {
  const Icon = getFileIcon(item.type === 'folder' ? 'folder' : item.mime_type)
  const iconColor = getFileIconColor(item.type === 'folder' ? 'folder' : item.mime_type)

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    onContextMenu(e, {
      id: item.id,
      type: item.type,
      name: item.name,
      starred: item.starred,
    })
  }

  const row = (
    <div
      onClick={() => onItemClick(item)}
      onContextMenu={handleContextMenu}
      className="group flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 border-b border-gray-100 cursor-pointer select-none transition-colors"
    >
      <div className={iconColor}>
        <Icon className="h-5 w-5" />
      </div>
      <span className="flex-1 text-sm text-gray-900 truncate min-w-0">{item.name}</span>
      {item.starred && (
        <Star className="h-3.5 w-3.5 text-yellow-400 fill-yellow-400 shrink-0" />
      )}
      <span className="text-xs text-gray-500 shrink-0 w-20 text-right">
        {item.type === 'folder' ? '--' : formatFileSize(item.file_size ?? 0)}
      </span>
      <span className="text-xs text-gray-500 shrink-0 w-28 text-right">
        {formatRelativeTime(item.updated_at)}
      </span>
    </div>
  )

  const draggableRow = (
    <DraggableItem item={item}>
      {row}
    </DraggableItem>
  )

  if (item.type === 'folder') {
    return (
      <DroppableFolder folderId={item.id}>
        {draggableRow}
      </DroppableFolder>
    )
  }

  return draggableRow
}

export default function DriveGridView({
  items,
  viewMode,
  onItemClick,
  onContextMenu,
}: DriveGridViewProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-16">
        <FolderIcon className="h-16 w-16 text-gray-300 mx-auto mb-4" />
        <h3 className="text-gray-500 font-medium">No files here</h3>
        <p className="text-sm text-gray-400 mt-1">Upload files or create a folder to get started</p>
      </div>
    )
  }

  // Separate folders and files, folders first
  const folders = items.filter((i) => i.type === 'folder')
  const files = items.filter((i) => i.type === 'file')
  const sorted = [...folders, ...files]

  if (viewMode === 'grid') {
    return (
      <div>
        {folders.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 px-1">
              Folders
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {folders.map((item) => (
                <GridCard
                  key={`folder-${item.id}`}
                  item={item}
                  onItemClick={onItemClick}
                  onContextMenu={onContextMenu}
                />
              ))}
            </div>
          </div>
        )}
        {files.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 px-1">
              Files
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {files.map((item) => (
                <GridCard
                  key={`file-${item.id}`}
                  item={item}
                  onItemClick={onItemClick}
                  onContextMenu={onContextMenu}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // List view
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-500 uppercase tracking-wider">
        <span className="w-5" />
        <span className="flex-1">Name</span>
        <span className="w-20 text-right">Size</span>
        <span className="w-28 text-right">Modified</span>
      </div>
      {sorted.map((item) =>
        item.type === 'folder' ? (
          <ListRow
            key={`folder-${item.id}`}
            item={item}
            onItemClick={onItemClick}
            onContextMenu={onContextMenu}
          />
        ) : (
          <ListRow
            key={`file-${item.id}`}
            item={item}
            onItemClick={onItemClick}
            onContextMenu={onContextMenu}
          />
        )
      )}
    </div>
  )
}

// Helper to convert API documents and folders into DriveItems
export function documentsToItems(
  docs: any[],
  subfolders: Folder[],
  currentFolderId: string | null
): DriveItem[] {
  const folderItems: DriveItem[] = subfolders
    .filter((f) => f.parent_id === currentFolderId)
    .map((f) => ({
      id: f.id,
      type: 'folder' as const,
      name: f.name,
      updated_at: f.updated_at,
      folder_id: f.parent_id,
    }))

  const fileItems: DriveItem[] = docs.map((doc: any) => ({
    id: doc.id,
    type: 'file' as const,
    name: doc.title || doc.original_filename || doc.filename,
    mime_type: doc.mime_type,
    file_size: doc.file_size,
    updated_at: doc.updated_at,
    starred: doc.starred,
    folder_id: doc.folder_id,
  }))

  return [...folderItems, ...fileItems]
}
