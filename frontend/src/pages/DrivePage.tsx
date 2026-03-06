import { useState, useCallback, useRef, useEffect, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DndContext, type DragEndEvent } from '@dnd-kit/core'
import { toast } from 'sonner'
import {
  listDocuments,
  getFolderTree,
  createFolder,
  listStarred,
  listRecent,
  moveDocument,
  moveFolder as moveFolderApi,
  uploadDocuments,
  bulkDelete,
  bulkMove,
  bulkStar,
  renameDocument,
  renameFolder as renameFolderApi,
  getDownloadUrl,
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
  FolderUp,
  Plus,
  LayoutList,
  LayoutGrid,
  Search,
  Star,
  Trash2,
  Clock,
  Folder as FolderIcon,
  ChevronRight,
  X,
  FolderInput,
  Download,
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
  const [isFolderUploading, setIsFolderUploading] = useState(false)
  const [showMoveDialog, setShowMoveDialog] = useState(false)
  const [moveTarget, setMoveTarget] = useState<{ id: string; type: 'file' | 'folder' } | null>(null)
  const [moveDestination, setMoveDestination] = useState<string | null>(null)

  // Rename dialog
  const [showRenameDialog, setShowRenameDialog] = useState(false)
  const [renameTarget, setRenameTarget] = useState<{ id: string; type: 'file' | 'folder'; currentName: string } | null>(null)
  const [renameValue, setRenameValue] = useState('')

  // Multi-select
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [lastClickedId, setLastClickedId] = useState<string | null>(null)

  // Bulk move
  const [showBulkMoveDialog, setShowBulkMoveDialog] = useState(false)
  const [bulkMoveDestination, setBulkMoveDestination] = useState<string | null>(null)

  // Context menu
  const [contextPos, setContextPos] = useState<ContextMenuPosition | null>(null)
  const [contextItem, setContextItem] = useState<ContextMenuItem | null>(null)

  const plusMenuRef = useRef<HTMLDivElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const debouncedSearch = useDebounce(searchQuery, 300)

  // ---- Data fetching ----

  const { data: foldersData } = useQuery({
    queryKey: ['folders'],
    queryFn: getFolderTree,
  })
  const folders = foldersData?.data ?? []

  const flatFolders = flattenFolders(folders)

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

  const { data: starredData, isLoading: starredLoading } = useQuery({
    queryKey: ['starred'],
    queryFn: listStarred,
    enabled: currentView === 'starred',
  })

  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['recent'],
    queryFn: listRecent,
    enabled: currentView === 'recent',
  })

  // ---- Invalidation helper ----
  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['folders'] })
    queryClient.invalidateQueries({ queryKey: ['starred'] })
    queryClient.invalidateQueries({ queryKey: ['recent'] })
    queryClient.invalidateQueries({ queryKey: ['trashed'] })
    queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
  }, [queryClient])

  // ---- Mutations ----

  const createFolderMutation = useMutation({
    mutationFn: (data: { name: string; parent_id?: string }) => createFolder(data),
    onSuccess: () => {
      invalidateAll()
      setShowNewFolderDialog(false)
      setNewFolderName('')
      toast.success('Folder created')
    },
    onError: (err: Error) => toast.error(err.message || 'Failed to create folder'),
  })

  const moveDocMutation = useMutation({
    mutationFn: ({ id, folderId }: { id: string; folderId: string | null }) =>
      moveDocument(id, folderId),
    onSuccess: () => {
      invalidateAll()
      toast.success('File moved')
    },
    onError: (err: Error) => toast.error(err.message || 'Failed to move file'),
  })

  const moveFolderMutation = useMutation({
    mutationFn: ({ id, parentId }: { id: string; parentId: string | null }) =>
      moveFolderApi(id, parentId),
    onSuccess: () => {
      invalidateAll()
      toast.success('Folder moved')
    },
    onError: (err: Error) => toast.error(err.message || 'Failed to move folder'),
  })

  const renameMutation = useMutation({
    mutationFn: async ({ id, type, name }: { id: string; type: 'file' | 'folder'; name: string }) => {
      if (type === 'folder') await renameFolderApi(id, name)
      else await renameDocument(id, name)
    },
    onSuccess: () => {
      invalidateAll()
      setShowRenameDialog(false)
      setRenameTarget(null)
      toast.success('Renamed')
    },
    onError: (err: Error) => toast.error(err.message || 'Rename failed'),
  })

  // Bulk mutations
  const bulkDeleteMutation = useMutation({
    mutationFn: ({ docIds, folderIds }: { docIds: string[]; folderIds: string[] }) =>
      bulkDelete(docIds, folderIds),
    onSuccess: (res) => {
      invalidateAll()
      setSelectedIds(new Set())
      const d = res.data
      toast.success(`Deleted ${d.documents_deleted} file(s), ${d.folders_deleted} folder(s)`)
    },
    onError: (err: Error) => toast.error(err.message || 'Bulk delete failed'),
  })

  const bulkMoveMutation = useMutation({
    mutationFn: ({ docIds, folderIds, target }: { docIds: string[]; folderIds: string[]; target: string | null }) =>
      bulkMove(docIds, folderIds, target),
    onSuccess: () => {
      invalidateAll()
      setSelectedIds(new Set())
      setShowBulkMoveDialog(false)
      toast.success('Items moved')
    },
    onError: (err: Error) => toast.error(err.message || 'Bulk move failed'),
  })

  const bulkStarMutation = useMutation({
    mutationFn: ({ docIds, folderIds, starred }: { docIds: string[]; folderIds: string[]; starred: boolean }) =>
      bulkStar(docIds, folderIds, starred),
    onSuccess: () => {
      invalidateAll()
      setSelectedIds(new Set())
      toast.success('Updated')
    },
    onError: (err: Error) => toast.error(err.message || 'Failed'),
  })

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
      type: (doc.mime_type ? 'file' : 'folder') as 'file' | 'folder',
      name: doc.name || doc.title || doc.original_filename || doc.filename,
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
      starred: doc.is_starred,
    }))
    isLoading = recentLoading
  }

  if (debouncedSearch && currentView !== 'all') {
    const q = debouncedSearch.toLowerCase()
    items = items.filter((i) => i.name.toLowerCase().includes(q))
  }

  // ---- Helpers for selection ----
  const getSelectedByType = useCallback(() => {
    const docIds: string[] = []
    const folderIds: string[] = []
    for (const id of selectedIds) {
      const item = items.find((i) => i.id === id)
      if (item) {
        if (item.type === 'file') docIds.push(id)
        else folderIds.push(id)
      }
    }
    return { docIds, folderIds }
  }, [selectedIds, items])

  // ---- Handlers ----

  const handleItemClick = useCallback(
    (item: DriveItem, e: React.MouseEvent) => {
      if (e.ctrlKey || e.metaKey) {
        // Toggle selection
        setSelectedIds((prev) => {
          const next = new Set(prev)
          if (next.has(item.id)) next.delete(item.id)
          else next.add(item.id)
          return next
        })
        setLastClickedId(item.id)
      } else if (e.shiftKey && lastClickedId) {
        // Range select
        const itemIndex = items.findIndex((i) => i.id === item.id)
        const lastIndex = items.findIndex((i) => i.id === lastClickedId)
        if (itemIndex >= 0 && lastIndex >= 0) {
          const start = Math.min(itemIndex, lastIndex)
          const end = Math.max(itemIndex, lastIndex)
          const rangeIds = items.slice(start, end + 1).map((i) => i.id)
          setSelectedIds((prev) => {
            const next = new Set(prev)
            rangeIds.forEach((id) => next.add(id))
            return next
          })
        }
      } else {
        // Single click: select only this item
        setSelectedIds(new Set([item.id]))
        setLastClickedId(item.id)
      }
    },
    [lastClickedId, items],
  )

  const handleItemDoubleClick = useCallback(
    (item: DriveItem) => {
      if (item.type === 'folder') {
        setCurrentView('all')
        setCurrentFolderId(item.id)
        setSelectedIds(new Set())
      } else {
        navigate(`/documents/${item.id}`)
      }
    },
    [navigate],
  )

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, item: ContextMenuItem) => {
      // If right-clicked item is not in selection, select it alone
      if (!selectedIds.has(item.id)) {
        setSelectedIds(new Set([item.id]))
      }
      setContextPos({ x: e.clientX, y: e.clientY })
      setContextItem(item)
    },
    [selectedIds],
  )

  const handleContextOpen = useCallback(
    (id: string) => {
      const item = contextItem
      if (item?.type === 'folder') {
        setCurrentView('all')
        setCurrentFolderId(id)
        setSelectedIds(new Set())
      } else {
        navigate(`/documents/${id}`)
      }
    },
    [contextItem, navigate],
  )

  const handleContextMove = useCallback((id: string, type: 'file' | 'folder') => {
    setMoveTarget({ id, type })
    setMoveDestination(null)
    setShowMoveDialog(true)
  }, [])

  const handleContextRename = useCallback((id: string, type: 'file' | 'folder', currentName: string) => {
    setRenameTarget({ id, type, currentName })
    setRenameValue(currentName)
    setShowRenameDialog(true)
  }, [])

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over) return

      const dragData = active.data.current as { item: DriveItem } | undefined
      if (!dragData) return

      const dropId = String(over.id)
      const match = dropId.match(/^drop-folder-(.+)$/)
      if (!match) return

      const targetFolderId = match[1]
      const draggedItem = dragData.item

      if (draggedItem.type === 'folder' && draggedItem.id === targetFolderId) return

      // If dragged item is selected, move all selected items
      if (selectedIds.has(draggedItem.id) && selectedIds.size > 1) {
        const { docIds, folderIds } = getSelectedByType()
        bulkMoveMutation.mutate({ docIds, folderIds, target: targetFolderId })
      } else {
        if (draggedItem.type === 'file') {
          moveDocMutation.mutate({ id: draggedItem.id, folderId: targetFolderId })
        } else {
          moveFolderMutation.mutate({ id: draggedItem.id, parentId: targetFolderId })
        }
      }
    },
    [moveDocMutation, moveFolderMutation, selectedIds, getSelectedByType, bulkMoveMutation],
  )

  const handleSidebarNavigate = (view: ViewType, folderId?: string | null) => {
    setCurrentView(view)
    setCurrentFolderId(folderId ?? null)
    setSearchQuery('')
    setSelectedIds(new Set())
  }

  const handleUploadComplete = () => {
    setShowUpload(false)
    queryClient.refetchQueries({ queryKey: ['documents'] })
    queryClient.refetchQueries({ queryKey: ['folders'] })
    queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
    queryClient.invalidateQueries({ queryKey: ['recent'] })
  }

  const handleFolderUploadClick = () => {
    setShowPlusMenu(false)
    folderInputRef.current?.click()
  }

  const handleFolderInputChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setIsFolderUploading(true)
    try {
      const result = await uploadDocuments(Array.from(files), currentFolderId ?? undefined)
      queryClient.refetchQueries({ queryKey: ['documents'] })
      queryClient.refetchQueries({ queryKey: ['folders'] })
      queryClient.invalidateQueries({ queryKey: ['storage-usage'] })
      queryClient.invalidateQueries({ queryKey: ['recent'] })
      const count = result.data.length
      const failCount = result.failures.length
      if (failCount > 0) {
        toast.warning(`Uploaded ${count} file(s), ${failCount} failed`)
      } else {
        toast.success(`Uploaded ${count} file(s)`)
      }
    } catch (err: any) {
      toast.error(err.message || 'Folder upload failed')
    } finally {
      setIsFolderUploading(false)
      e.target.value = ''
    }
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

  // ---- Bulk action handlers ----
  const handleBulkDelete = () => {
    const { docIds, folderIds } = getSelectedByType()
    const total = docIds.length + folderIds.length
    if (confirm(`Delete ${total} item(s)? This cannot be undone.`)) {
      bulkDeleteMutation.mutate({ docIds, folderIds })
    }
  }

  const handleBulkStar = () => {
    const { docIds, folderIds } = getSelectedByType()
    bulkStarMutation.mutate({ docIds, folderIds, starred: true })
  }

  const handleBulkDownload = () => {
    const { docIds } = getSelectedByType()
    for (const id of docIds) {
      const a = document.createElement('a')
      a.href = getDownloadUrl(id)
      a.download = ''
      a.click()
    }
    toast.success(`Downloading ${docIds.length} file(s)`)
  }

  const handleBulkMoveConfirm = () => {
    const { docIds, folderIds } = getSelectedByType()
    bulkMoveMutation.mutate({ docIds, folderIds, target: bulkMoveDestination })
  }

  // ---- Keyboard: Escape clears selection ----
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedIds(new Set())
        setContextPos(null)
        setContextItem(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Clear selection when clicking on empty area
  const handleContentAreaClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setSelectedIds(new Set())
    }
  }

  return (
    <div className="flex h-[calc(100vh-49px)]">
      {/* Hidden folder upload input */}
      <input
        ref={folderInputRef}
        type="file"
        className="hidden"
        onChange={handleFolderInputChange}
        /* @ts-expect-error webkitdirectory is non-standard but widely supported */
        webkitdirectory=""
        multiple
      />

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
                  onClick={handleFolderUploadClick}
                  disabled={isFolderUploading}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
                >
                  <FolderUp className="h-4 w-4" />
                  {isFolderUploading ? 'Uploading...' : 'Upload Folder'}
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
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50',
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
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50',
              )}
              title="List view"
            >
              <LayoutList className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Selection toolbar */}
        {selectedIds.size >= 2 && (
          <div className="bg-blue-50 dark:bg-blue-900/30 border-b border-blue-200 dark:border-blue-800 px-4 py-2 flex items-center gap-3">
            <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
              {selectedIds.size} items selected
            </span>
            <div className="flex-1" />
            <button
              onClick={handleBulkStar}
              disabled={bulkStarMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              <Star className="h-3.5 w-3.5" />
              Star All
            </button>
            <button
              onClick={() => {
                setBulkMoveDestination(null)
                setShowBulkMoveDialog(true)
              }}
              disabled={bulkMoveMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              <FolderInput className="h-3.5 w-3.5" />
              Move All
            </button>
            <button
              onClick={handleBulkDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Download All
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={bulkDeleteMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-600 bg-white dark:bg-gray-800 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {bulkDeleteMutation.isPending ? 'Deleting...' : 'Delete All'}
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="p-1.5 text-gray-500 hover:text-gray-700 transition-colors"
              title="Clear selection"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Breadcrumb bar */}
        {currentView === 'all' && (
          <div className="bg-white dark:bg-gray-900 border-b px-4 py-2">
            <DriveBreadcrumb
              currentFolderId={currentFolderId}
              folders={folders}
              onNavigate={(id) => {
                setCurrentFolderId(id)
                setSelectedIds(new Set())
              }}
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
        <div
          className="flex-1 overflow-y-auto p-4"
          onClick={handleContentAreaClick}
        >
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
                selectedIds={selectedIds}
                onItemClick={handleItemClick}
                onItemDoubleClick={handleItemDoubleClick}
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
        onRename={handleContextRename}
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

      {/* ===== Rename Dialog ===== */}
      {showRenameDialog && renameTarget && (
        <DialogOverlay onClose={() => setShowRenameDialog(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Rename</h3>
            <input
              type="text"
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder="New name"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && renameValue.trim()) {
                  renameMutation.mutate({ id: renameTarget.id, type: renameTarget.type, name: renameValue.trim() })
                }
              }}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowRenameDialog(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (renameValue.trim()) {
                    renameMutation.mutate({ id: renameTarget.id, type: renameTarget.type, name: renameValue.trim() })
                  }
                }}
                disabled={!renameValue.trim() || renameMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {renameMutation.isPending ? 'Renaming...' : 'Rename'}
              </button>
            </div>
          </div>
        </DialogOverlay>
      )}

      {/* ===== Move Dialog (single item) ===== */}
      {showMoveDialog && moveTarget && (
        <DialogOverlay onClose={() => setShowMoveDialog(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Move to...</h3>
            <FolderPicker
              folders={flatFolders}
              excludeId={moveTarget.id}
              selected={moveDestination}
              onSelect={setMoveDestination}
            />
            <div className="flex justify-end gap-2 mt-4">
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

      {/* ===== Bulk Move Dialog ===== */}
      {showBulkMoveDialog && (
        <DialogOverlay onClose={() => setShowBulkMoveDialog(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Move {selectedIds.size} items to...
            </h3>
            <FolderPicker
              folders={flatFolders}
              selected={bulkMoveDestination}
              onSelect={setBulkMoveDestination}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowBulkMoveDialog(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkMoveConfirm}
                disabled={bulkMoveMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {bulkMoveMutation.isPending ? 'Moving...' : 'Move here'}
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

// ===== Reusable sub-components =====

function FolderPicker({
  folders,
  excludeId,
  selected,
  onSelect,
}: {
  folders: FlatFolder[]
  excludeId?: string
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  return (
    <div className="max-h-60 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg">
      <button
        onClick={() => onSelect(null)}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors',
          selected === null ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium' : 'text-gray-700 dark:text-gray-300',
        )}
      >
        <FolderIcon className="h-4 w-4" />
        My Drive (root)
      </button>
      {folders
        .filter((f) => f.id !== excludeId)
        .map((folder) => (
          <button
            key={folder.id}
            onClick={() => onSelect(folder.id)}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors',
              selected === folder.id
                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 font-medium'
                : 'text-gray-700 dark:text-gray-300',
            )}
            style={{ paddingLeft: `${(folder._depth ?? 0) * 16 + 12}px` }}
          >
            <FolderIcon className="h-4 w-4" />
            {folder.name}
          </button>
        ))}
    </div>
  )
}

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
          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100',
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
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100',
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
