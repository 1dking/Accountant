import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listDocuments, getFolderTree } from '@/api/documents'
import DocumentCard from '@/components/documents/DocumentCard'
import FolderTree from '@/components/documents/FolderTree'
import UploadZone from '@/components/documents/UploadZone'
import UploadBookingDialog from '@/components/documents/UploadBookingDialog'
import { useDebounce } from '@/hooks/useDebounce'
import { DOCUMENT_TYPES, DOCUMENT_STATUSES } from '@/lib/constants'
import type { DocumentFilters } from '@/types/api'

export default function DocumentsPage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showUpload, setShowUpload] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [showBookingDialog, setShowBookingDialog] = useState(false)

  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)

  const debouncedSearch = useDebounce(search, 300)

  const filters: DocumentFilters = {
    search: debouncedSearch || undefined,
    folder_id: selectedFolder || undefined,
    document_type: typeFilter || undefined,
    status: statusFilter || undefined,
    page,
    page_size: 25,
    sort_by: 'created_at',
    sort_order: 'desc',
  }

  const { data: docsData, isLoading, error } = useQuery({
    queryKey: ['documents', filters],
    queryFn: () => listDocuments(filters),
  })

  const { data: foldersData } = useQuery({
    queryKey: ['folders'],
    queryFn: getFolderTree,
  })

  const documents = docsData?.data ?? []
  const meta = docsData?.meta
  const folders = foldersData?.data ?? []

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleUploadComplete = () => {
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    setShowUpload(false)
  }

  const handleFilesSelected = (files: File[]) => {
    setPendingFiles(files)
    setShowBookingDialog(true)
  }

  const handleBookingComplete = () => {
    setShowBookingDialog(false)
    setPendingFiles([])
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
    queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
    setShowUpload(false)
  }

  const handleBookingClose = () => {
    setShowBookingDialog(false)
    setPendingFiles([])
  }

  return (
    <div className="flex h-[calc(100vh-49px)]">
      {/* Folder sidebar */}
      <div className="w-56 border-r bg-white p-3 overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Folders</h3>
        </div>
        <FolderTree
          folders={folders}
          selectedFolderId={selectedFolder}
          onSelect={setSelectedFolder}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="bg-white border-b px-4 py-3 flex items-center gap-3 flex-wrap">
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            placeholder="Search documents..."
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
          />
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value)
              setPage(1)
            }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white"
          >
            <option value="">All Types</option>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white"
          >
            <option value="">All Statuses</option>
            {DOCUMENT_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <div className="flex-1" />
          {selectedIds.size > 0 && (
            <span className="text-sm text-gray-500">{selectedIds.size} selected</span>
          )}
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            Upload
          </button>
        </div>

        {/* Upload zone */}
        {showUpload && (
          <div className="bg-gray-50 border-b p-4">
            <UploadZone folderId={selectedFolder ?? undefined} onFilesSelected={handleFilesSelected} onUploadComplete={handleUploadComplete} />
          </div>
        )}

        {/* Document list */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">&#9888;</div>
              <h3 className="text-red-600 font-medium">Failed to load documents</h3>
              <p className="text-sm text-gray-500 mt-1">
                {error instanceof Error ? error.message : 'Unknown error'}
              </p>
              <button
                onClick={() => queryClient.invalidateQueries({ queryKey: ['documents'] })}
                className="mt-3 px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                Retry
              </button>
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">{'\uD83D\uDCC2'}</div>
              <h3 className="text-gray-900 font-medium">No documents found</h3>
              <p className="text-sm text-gray-500 mt-1">
                {search || typeFilter || statusFilter
                  ? 'Try adjusting your filters'
                  : 'Upload your first document to get started'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  selected={selectedIds.has(doc.id)}
                  onSelect={toggleSelect}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 text-sm border rounded-md disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {meta.page} of {meta.total_pages} ({meta.total_count} documents)
              </span>
              <button
                onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
                disabled={page >= meta.total_pages}
                className="px-3 py-1 text-sm border rounded-md disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>

      <UploadBookingDialog
        isOpen={showBookingDialog}
        files={pendingFiles}
        folderId={selectedFolder ?? undefined}
        onClose={handleBookingClose}
        onComplete={handleBookingComplete}
      />
    </div>
  )
}
