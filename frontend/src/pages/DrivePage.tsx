import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, type DragEndEvent } from '@dnd-kit/core'
import {
  listDocuments,
  getFolderTree,
  createFolder,
  listStarred,
  listRecent,
  moveDocument,
  moveFolder as moveFolderApi,
} from '@/api/documents'
import DriveGridView, { documentsToItems, type DriveItem } from '@/components/documents/DriveGridView'
import DriveBreadcrumb from '@/components/documents/DriveBreadcrumb'
import FileContextMenu, {
  type ContextMenuPosition,
  type ContextMenuItem,
} from '@/components/documents/FileContextMenu'
import StorageUsage from '@/components/documents/StorageUsage'
import TrashView from '@/components/documents/TrashView'
import UploadZone from '@/components/documents/UploadZone'
import { useDebounce } from '@/hooks/useDebounce'
import { cn } from '@/lib/utils'
import type { Folder } from '@/types/models'
import {
  Upload,
  FolderPlus,
  Plus,
  LayoutList,
  LayoutGrid,
  Search,
  Star,
  Trash2,
  Clock,
  Folder as FolderIcon,
  ChevronRight,
} from 'lucide-react'

type ViewType = 'all' | 'starred' | 'recent' | 'trash'

export default function DrivePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // State
  const [currentView, setCurrentView] = useState<ViewType>('all')
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [showPlusMenu, setShowPlusMenu] = useState(false)
  const [showMoveDialog, setShowMoveDialog] = useState(false)
  const [moveTarget, setMoveTarget] = useState<{ id: string; type: 'file' | 'folder' } | null>(null)
  const [moveDestination, setMoveDestination] = useState<string | null>(null)

  // Context menu
  const [contextPos, setContextPos] = useState<ContextMenuPosition | null>(null)
  const [contextItem, setContextItem] = useState<ContextMenuItem | null>(null)

  const plusMenuRef = useRef<HTMLDivElement>(null)
  const debouncedSearch = useDebounce(searchQuery, 300)

  // ---- Data fetching ----

  // Folder tree (always loaded)
  const { data: foldersData } = useQuery({
    queryKey: ['folders'],
    queryFn: getFolderTree,
  })
  const folders = foldersData?.data ?? []

  // Flatten folders for subfolder display
  const flatFolders = flattenFolders(folders)

  // Documents in current folder
  const { data: docsData, isLoading: docsLoading } = useQuery({
    queryKey: ['documents', { folder_id: currentFolderId, search: debouncedSearch }],
    queryFn: () =>
      listDocuments({
        folder_id: currentFolderId ?? undefined,
        search: debouncedSearch || undefined,
        page_size: 200,
        sort_by: 'created_at',
        sort_order: 'desc',
      }),
    enabled: currentView === 'all',
  })

  // Starred
  const { data: starredData, isLoading: starredLoading } = useQuery({
    queryKey: ['starred'],
    queryFn: listStarred,
    enabled: currentView === 'starred',
  })

  // Recent
  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['recent'],
    queryFn: listRecent,
    enabled: currentView === 'recent',
  })

  // ---- Mutations ----

  const createFolderMutation = useMutation({
    mutationFn: (data: { name: string; parent_id?: string }) => createFolder(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders'] })
      queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
      setShowNewFolderDialog(false)
      setNewFolderName('')
    },
  })

  const moveDocMutation = useMutation({
    mutationFn: ({ id, folderId }: { id: string; folderId: string | null }) =>
      moveDocument(id, folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['folders'] })
      queryClient.invalidateQueries({ queryKey: ['starred'] })
      queryClient.invalidateQueries({ queryKey: ['recent'] })
    },
  })

  const moveFolderMutation = useMutation({
    mutationFn: ({ id, parentId }: { id: string; parentId: string | null }) =>
      moveFolderApi(id, parentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders'] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  // ---- Handlers ----

  const handleItemClick = useCallback(
    (item: DriveItem) => {
      if (item.type === 'folder') {
        setCurrentView('all')
        setCurrentFolderId(item.id)
      } else {
        navigate(`/documents/${item.id}`)
      }
    },
    [navigate]
  )

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, item: ContextMenuItem) => {
      setContextPos({ x: e.clientX, y: e.clientY })
      setContextItem(item)
    },
    []
  )

  const handleContextOpen = useCallback(
    (id: string) => {
      const item = contextItem
      if (item?.type === 'folder') {
        setCurrentView('all')
        setCurrentFolderId(id)
      } else {
        navigate(`/documents/${id}`)
      }
    },
    [contextItem, navigate]
  )

  const handleContextMove = useCallback((id: string, type: 'file' | 'folder') => {
    setMoveTarget({ id, type })
    setMoveDestination(null)
    setShowMoveDialog(true)
  }, [])

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over) return

      const dragData = active.data.current as { item: DriveItem } | undefined
      if (!dragData) return

      const dropId = String(over.id)
      // Extract folder id from the droppable id: "drop-folder-{id}"
      const match = dropId.match(/^drop-folder-(.+)$/)
      if (!match) return

      const targetFolderId = match[1]
      const draggedItem = dragData.item

      // Don't drop folder on itself
      if (draggedItem.type === 'folder' && draggedItem.id === targetFolderId) return

      if (draggedItem.type === 'file') {
        moveDocMutation.mutate({ id: draggedItem.id, folderId: targetFolderId })
      } else {
        moveFolderMutation.mutate({ id: draggedItem.id, parentId: targetFolderId })
      }
    },
    [moveDocMutation, moveFolderMutation]
  )

  const handleSidebarNavigate = (view: ViewType, folderId?: string | null) => {
    setCurrentView(view)
    setCurrentFolderId(folderId ?? null)
    setSearchQuery('')
  }

  const handleUploadComplete = () => {
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
    queryClient.invalidateQueries({ queryKey: ['recent'] })
    setShowUpload(false)
  }

  const handleConfirmMove = () => {
    if (!moveTarget) return
    if (moveTarget.type === 'file') {
      moveDocMutation.mutate({ id: moveTarget.id, folderId: moveDestination })
    } else {
      moveFolderMutation.mutate({ id: moveTarget.id, parentId: moveDestination })
    }
    setShowMoveDialog(false)
    setMoveTarget(null)
  }

  // ---- Build items for current view ----

  let items: DriveItem[] = []
  let isLoading = false

  if (currentView === 'all') {
    const docs = docsData?.data ?? []
    items = documentsToItems(docs, flatFolders, currentFolderId)
    isLoading = docsLoading
  } else if (currentView === 'starred') {
    const starred = starredData?.data ?? []
    items = starred.map((doc: any) => ({
      id: doc.id,
      type: 'file' as const,
      name: doc.title || doc.original_filename || doc.filename,
      mime_type: doc.mime_type,
      file_size: doc.file_size,
      updated_at: doc.updated_at,
      starred: true,
    }))
    isLoading = starredLoading
  } else if (currentView === 'recent') {
    const recent = recentData?.data ?? []
    items = recent.map((doc: any) => ({
      id: doc.id,
      type: 'file' as const,
      name: doc.title || doc.original_filename || doc.filename,
      mime_type: doc.mime_type,
      file_size: doc.file_size,
      updated_at: doc.updated_at,
      starred: doc.starred,
    }))
    isLoading = recentLoading
  }

  // Filter by search in non-all views
  if (debouncedSearch && currentView !== 'all') {
    const q = debouncedSearch.toLowerCase()
    items = items.filter((i) => i.name.toLowerCase().includes(q))
  }

  return (
    <div className="flex h-[calc(100vh-49px)]">
      {/* ===== Left Sidebar ===== */}
      <div className="w-56 border-r bg-white dark:bg-gray-900 flex flex-col overflow-y-auto shrink-0">
        <div className="p-3 space-y-0.5">
          <SidebarButton
            active={currentView === 'all' && currentFolderId === null}
            icon={FolderIcon}
            label="All Files"
            onClick={() => handleSidebarNavigate('all', null)}
          />
          <SidebarButton
            active={currentView === 'starred'}
            icon={Star}
            label="Starred"
            onClick={() => handleSidebarNavigate('starred')}
          />
          <SidebarButton
            active={currentView === 'recent'}
            icon={Clock}
            label="Recent"
            onClick={() => handleSidebarNavigate('recent')}
          />
          <SidebarButton
            active={currentView === 'trash'}
            icon={Trash2}
            label="Trash"
            onClick={() => handleSidebarNavigate('trash')}
          />
        </div>

        {/* Folder tree */}
        <div className="px-3 pb-2">
          <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 px-2">
            Folders
          </h4>
          <SidebarFolderTree
            folders={folders}
            currentFolderId={currentFolderId}
            currentView={currentView}
            onSelect={(id) => handleSidebarNavigate('all', id)}
          />
        </div>

        {/* Storage usage at bottom */}
        <div className="mt-auto">
          <StorageUsage />
        </div>
      </div>

      {/* ===== Main Content ===== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top toolbar */}
        <div className="bg-white dark:bg-gray-900 border-b px-4 py-2.5 flex items-center gap-3">
          {/* Plus menu */}
          <div className="relative" ref={plusMenuRef}>
            <button
              onClick={() => setShowPlusMenu(!showPlusMenu)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              New
            </button>
            {showPlusMenu && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 z-40">
                <button
                  onClick={() => {
                    setShowUpload(true)
                    setShowPlusMenu(false)
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <Upload className="h-4 w-4" />
                  Upload File
                </button>
                <button
                  onClick={() => {
                    setShowNewFolderDialog(true)
                    setShowPlusMenu(false)
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <FolderPlus className="h-4 w-4" />
                  New Folder
                </button>
              </div>
            )}
          </div>

          {/* Upload / New Folder direct buttons */}
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <Upload className="h-4 w-4" />
            Upload
          </button>
          <button
            onClick={() => setShowNewFolderDialog(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <FolderPlus className="h-4 w-4" />
            New Folder
          </button>

          <div className="flex-1" />

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
            <input
              type="search"
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
            />
          </div>

          {/* View toggle */}
          <div className="flex items-center border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-1.5 transition-colors',
                viewMode === 'grid'
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600'
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50'
              )}
              title="Grid view"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'p-1.5 transition-colors',
                viewMode === 'list'
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600'
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50'
              )}
              title="List view"
            >
              <LayoutList className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Breadcrumb bar */}
        {currentView === 'all' && (
          <div className="bg-white dark:bg-gray-900 border-b px-4 py-2">
            <DriveBreadcrumb
              currentFolderId={currentFolderId}
              folders={folders}
              onNavigate={(id) => setCurrentFolderId(id)}
            />
          </div>
        )}

        {/* Upload zone (toggled) */}
        {showUpload && (
          <div className="bg-gray-50 dark:bg-gray-950 border-b p-4">
            <UploadZone
              folderId={currentFolderId ?? undefined}
              onUploadComplete={handleUploadComplete}
            />
          </div>
        )}

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-4">
          {currentView === 'trash' ? (
            <TrashView />
          ) : isLoading ? (
            <div className="space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-20 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : (
            <DndContext onDragEnd={handleDragEnd}>
              <DriveGridView
                items={items}
                viewMode={viewMode}
                onItemClick={handleItemClick}
                onContextMenu={handleContextMenu}
              />
            </DndContext>
          )}
        </div>
      </div>

      {/* ===== Context Menu ===== */}
      <FileContextMenu
        position={contextPos}
        item={contextItem}
        onClose={() => {
          setContextPos(null)
          setContextItem(null)
        }}
        onOpen={handleContextOpen}
        onMove={handleContextMove}
      />

      {/* ===== New Folder Dialog ===== */}
      {showNewFolderDialog && (
        <DialogOverlay onClose={() => setShowNewFolderDialog(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">New Folder</h3>
            <input
              type="text"
              autoFocus
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="Folder name"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newFolderName.trim()) {
                  createFolderMutation.mutate({
                    name: newFolderName.trim(),
                    parent_id: currentFolderId ?? undefined,
                  })
                }
              }}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowNewFolderDialog(false)
                  setNewFolderName('')
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (newFolderName.trim()) {
                    createFolderMutation.mutate({
                      name: newFolderName.trim(),
                      parent_id: currentFolderId ?? undefined,
                    })
                  }
                }}
                disabled={!newFolderName.trim() || createFolderMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {createFolderMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </DialogOverlay>
      )}

      {/* ===== Move Dialog ===== */}
      {showMoveDialog && moveTarget && (
        <DialogOverlay onClose={() => setShowMoveDialog(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Move to...</h3>
            <div className="max-h-60 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
              <button
                onClick={() => setMoveDestination(null)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors',
                  moveDestination === null ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium' : 'text-gray-700'
                )}
              >
                <FolderIcon className="h-4 w-4" />
                My Drive (root)
              </button>
              {flatFolders
                .filter((f) => f.id !== moveTarget.id)
                .map((folder) => (
                  <button
                    key={folder.id}
                    onClick={() => setMoveDestination(folder.id)}
                    className={cn(
                      'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors',
                      moveDestination === folder.id
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
                        : 'text-gray-700'
                    )}
                    style={{ paddingLeft: `${(folder._depth ?? 0) * 16 + 12}px` }}
                  >
                    <FolderIcon className="h-4 w-4" />
                    {folder.name}
                  </button>
                ))}
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowMoveDialog(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmMove}
                disabled={moveDocMutation.isPending || moveFolderMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                Move here
              </button>
            </div>
          </div>
        </DialogOverlay>
      )}

      {/* Click-away for plus menu */}
      {showPlusMenu && (
        <div
          className="fixed inset-0 z-30"
          onClick={() => setShowPlusMenu(false)}
        />
      )}
    </div>
  )
}

// ===== Helper Components =====

function SidebarButton({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean
  icon: React.ComponentType<{ className?: string }>
  label: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-colors',
        active
          ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100'
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  )
}

function SidebarFolderTree({
  folders,
  currentFolderId,
  currentView,
  onSelect,
}: {
  folders: Folder[]
  currentFolderId: string | null
  currentView: ViewType
  onSelect: (id: string) => void
}) {
  return (
    <div className="space-y-0.5">
      {folders.map((folder) => (
        <SidebarFolderNode
          key={folder.id}
          folder={folder}
          currentFolderId={currentFolderId}
          currentView={currentView}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  )
}

function SidebarFolderNode({
  folder,
  currentFolderId,
  currentView,
  onSelect,
  depth,
}: {
  folder: Folder
  currentFolderId: string | null
  currentView: ViewType
  onSelect: (id: string) => void
  depth: number
}) {
  const [expanded, setExpanded] = useState(false)
  const hasChildren = folder.children && folder.children.length > 0
  const isActive = currentView === 'all' && currentFolderId === folder.id

  return (
    <div>
      <div className="flex items-center">
        {hasChildren ? (
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-0.5 text-gray-400 dark:text-gray-500 hover:text-gray-600"
            style={{ marginLeft: `${depth * 12}px` }}
          >
            <ChevronRight
              className={cn('h-3.5 w-3.5 transition-transform', expanded && 'rotate-90')}
            />
          </button>
        ) : (
          <span style={{ marginLeft: `${depth * 12 + 18}px` }} />
        )}
        <button
          onClick={() => onSelect(folder.id)}
          className={cn(
            'flex-1 flex items-center gap-1.5 px-2 py-1 text-sm rounded-md transition-colors truncate',
            isActive
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100'
          )}
        >
          <FolderIcon className="h-4 w-4 text-blue-500 shrink-0" />
          <span className="truncate">{folder.name}</span>
        </button>
      </div>
      {hasChildren && expanded && (
        <div>
          {folder.children!.map((child) => (
            <SidebarFolderNode
              key={child.id}
              folder={child}
              currentFolderId={currentFolderId}
              currentView={currentView}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function DialogOverlay({
  children,
  onClose,
}: {
  children: React.ReactNode
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10">{children}</div>
    </div>
  )
}

// ===== Helpers =====

interface FlatFolder extends Folder {
  _depth: number
}

function flattenFolders(folders: Folder[], depth = 0): FlatFolder[] {
  const result: FlatFolder[] = []
  for (const f of folders) {
    result.push({ ...f, _depth: depth })
    if (f.children) {
      result.push(...flattenFolders(f.children, depth + 1))
    }
  }
  return result
}
