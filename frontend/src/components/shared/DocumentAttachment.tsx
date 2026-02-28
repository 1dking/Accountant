import { useState, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Upload, Paperclip, X, Loader2, FolderOpen } from 'lucide-react'
import { uploadDocuments, listDocuments, getDocument } from '@/api/documents'
import { useDebounce } from '@/hooks/useDebounce'
import { formatFileSize } from '@/lib/utils'
import type { DocumentListItem } from '@/types/models'

interface DocumentAttachmentProps {
  selectedDocument: DocumentListItem | null
  onDocumentSelect: (doc: DocumentListItem | null) => void
  onMetadataExtracted?: (metadata: Record<string, any>) => void
  label?: string
}

export default function DocumentAttachment({
  selectedDocument,
  onDocumentSelect,
  onMetadataExtracted,
  label = 'Linked Document',
}: DocumentAttachmentProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [showDrivePicker, setShowDrivePicker] = useState(false)
  const [documentSearch, setDocumentSearch] = useState('')

  const debouncedDocSearch = useDebounce(documentSearch, 300)

  const { data: docsData } = useQuery({
    queryKey: ['documents', { search: debouncedDocSearch }],
    queryFn: () => listDocuments({ search: debouncedDocSearch || undefined, page_size: 20 }),
    enabled: showDrivePicker,
  })
  const searchedDocs = docsData?.data ?? []

  const handleFileUpload = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const res = await uploadDocuments([file])
        const uploaded = res.data[0]
        if (!uploaded) return

        // Build a DocumentListItem from the uploaded Document
        const docListItem: DocumentListItem = {
          id: uploaded.id,
          filename: uploaded.filename,
          original_filename: uploaded.original_filename,
          mime_type: uploaded.mime_type,
          file_size: uploaded.file_size,
          document_type: uploaded.document_type,
          status: uploaded.status,
          title: uploaded.title,
          folder_id: uploaded.folder_id,
          uploaded_by: uploaded.uploaded_by,
          tags: uploaded.tags,
          created_at: uploaded.created_at,
          updated_at: uploaded.updated_at,
        }
        onDocumentSelect(docListItem)

        // Fetch full document to get extracted metadata
        try {
          const fullDoc = await getDocument(uploaded.id)
          const meta = fullDoc.data?.extracted_metadata as Record<string, any> | null | undefined
          if (meta && onMetadataExtracted) {
            onMetadataExtracted(meta)
          }
        } catch {
          // best-effort metadata extraction
        }
      } catch {
        // upload failed silently
      } finally {
        setUploading(false)
      }
    },
    [onDocumentSelect, onMetadataExtracted],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setDragOver(false)
      const file = e.dataTransfer.files?.[0]
      if (file) {
        handleFileUpload(file)
      }
    },
    [handleFileUpload],
  )

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }, [])

  const handleDragEnter = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }, [])

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        handleFileUpload(file)
      }
      // Reset input so the same file can be re-selected
      e.target.value = ''
    },
    [handleFileUpload],
  )

  const handleDriveDocSelect = useCallback(
    async (doc: DocumentListItem) => {
      onDocumentSelect(doc)
      setDocumentSearch('')
      setShowDrivePicker(false)

      try {
        const res = await getDocument(doc.id)
        const meta = res.data?.extracted_metadata as Record<string, any> | null | undefined
        if (meta && onMetadataExtracted) {
          onMetadataExtracted(meta)
        }
      } catch {
        // best-effort
      }
    },
    [onDocumentSelect, onMetadataExtracted],
  )

  // Attached document display
  if (selectedDocument) {
    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          <Paperclip className="inline h-3.5 w-3.5 mr-1" />
          {label}
        </label>
        <div className="flex items-center gap-2 w-full px-3 py-2 text-sm border rounded-md bg-gray-50">
          <Paperclip className="h-4 w-4 text-gray-400 shrink-0" />
          <span className="flex-1 truncate">
            {selectedDocument.title || selectedDocument.original_filename}
            <span className="text-gray-400 ml-2">{formatFileSize(selectedDocument.file_size)}</span>
          </span>
          <button
            type="button"
            onClick={() => onDocumentSelect(null)}
            className="text-gray-400 hover:text-red-500"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        <Paperclip className="inline h-3.5 w-3.5 mr-1" />
        {label}
      </label>

      {/* Upload zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-6 w-6 text-blue-500 animate-spin" />
            <p className="text-sm text-gray-500">Uploading...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-6 w-6 text-gray-400" />
            <p className="text-sm text-gray-500">
              Drag & drop a file or{' '}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Browse
              </button>
            </p>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileInputChange}
          className="hidden"
        />
      </div>

      {/* Choose from Drive button */}
      <button
        type="button"
        onClick={() => setShowDrivePicker(!showDrivePicker)}
        className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm border rounded-md text-gray-600 hover:bg-gray-50 transition-colors"
      >
        <FolderOpen className="h-4 w-4" />
        Choose from Drive
      </button>

      {/* Drive picker */}
      {showDrivePicker && (
        <div className="mt-2 border rounded-md overflow-hidden">
          <div className="p-2 border-b bg-gray-50">
            <input
              type="text"
              value={documentSearch}
              onChange={(e) => setDocumentSearch(e.target.value)}
              placeholder="Filter documents..."
              className="w-full px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="max-h-48 overflow-y-auto">
            {searchedDocs.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">
                No documents found
              </div>
            ) : (
              searchedDocs.map((doc) => (
                <button
                  key={doc.id}
                  type="button"
                  onClick={() => handleDriveDocSelect(doc)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 flex items-center justify-between border-b last:border-b-0"
                >
                  <span className="truncate">
                    {doc.title || doc.original_filename}
                  </span>
                  <span className="text-xs text-gray-400 ml-2 shrink-0">
                    {formatFileSize(doc.file_size)}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
