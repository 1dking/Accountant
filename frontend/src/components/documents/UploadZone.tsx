import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { uploadDocuments } from '@/api/documents'
import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE } from '@/lib/constants'
import { formatFileSize } from '@/lib/utils'

interface UploadZoneProps {
  folderId?: string
  onUploadComplete?: () => void
  onFilesSelected?: (files: File[]) => void
  compact?: boolean
}

interface UploadProgress {
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  error?: string
}

export default function UploadZone({ folderId, onUploadComplete, onFilesSelected, compact }: UploadZoneProps) {
  const [uploads, setUploads] = useState<UploadProgress[]>([])
  const [isUploading, setIsUploading] = useState(false)

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return

      // If parent wants to intercept file selection, delegate to it
      if (onFilesSelected) {
        onFilesSelected(acceptedFiles)
        return
      }

      const items: UploadProgress[] = acceptedFiles.map((file) => ({
        file,
        status: 'uploading' as const,
      }))
      setUploads(items)
      setIsUploading(true)

      try {
        await uploadDocuments(acceptedFiles, folderId)
        setUploads((prev) => prev.map((u) => ({ ...u, status: 'done' as const })))
        onUploadComplete?.()
        setTimeout(() => setUploads([]), 2000)
      } catch (err: any) {
        setUploads((prev) =>
          prev.map((u) => ({ ...u, status: 'error' as const, error: err.message }))
        )
      } finally {
        setIsUploading(false)
      }
    },
    [folderId, onUploadComplete, onFilesSelected]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    disabled: isUploading,
  })

  if (compact) {
    return (
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-sm text-gray-500">
          {isDragActive ? 'Drop files here' : 'Drop files or click to upload'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
        } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-2">{'\uD83D\uDCC1'}</div>
        <p className="text-gray-700 font-medium">
          {isDragActive ? 'Drop files here...' : 'Drag & drop files here'}
        </p>
        <p className="text-sm text-gray-500 mt-1">
          or click to select files (max {formatFileSize(MAX_FILE_SIZE)} each)
        </p>
      </div>

      {uploads.length > 0 && (
        <div className="space-y-2">
          {uploads.map((u, i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-2 bg-white border rounded-md text-sm"
            >
              <span className="flex-1 truncate text-gray-700">{u.file.name}</span>
              <span className="text-gray-400">{formatFileSize(u.file.size)}</span>
              {u.status === 'uploading' && (
                <span className="text-blue-600">Uploading...</span>
              )}
              {u.status === 'done' && <span className="text-green-600">Done</span>}
              {u.status === 'error' && (
                <span className="text-red-600" title={u.error}>
                  Failed
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
