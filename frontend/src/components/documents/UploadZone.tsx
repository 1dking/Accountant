import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { uploadDocuments, type UploadResult } from '@/api/documents'
import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE } from '@/lib/constants'
import { formatFileSize } from '@/lib/utils'
import { FolderUp } from 'lucide-react'

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
  const [summary, setSummary] = useState<{ success: number; failed: number } | null>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  const doUpload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return

      // If parent wants to intercept file selection, delegate to it
      if (onFilesSelected) {
        onFilesSelected(files)
        return
      }

      const items: UploadProgress[] = files.map((file) => ({
        file,
        status: 'pending' as const,
      }))
      setUploads(items)
      setIsUploading(true)
      setSummary(null)

      try {
        const result = await uploadDocuments(files, folderId, undefined, (fileResult: UploadResult, index: number) => {
          setUploads((prev) =>
            prev.map((u, i) => {
              if (i === index) {
                return fileResult.error
                  ? { ...u, status: 'error' as const, error: fileResult.error }
                  : { ...u, status: 'done' as const }
              }
              if (i === index + 1 && u.status === 'pending') {
                return { ...u, status: 'uploading' as const }
              }
              return u
            })
          )
        })

        const successCount = result.data.length
        const failCount = result.failures?.length ?? 0
        setSummary({ success: successCount, failed: failCount })
        onUploadComplete?.()

        // Clear upload list after delay if all succeeded
        if (failCount === 0) {
          setTimeout(() => {
            setUploads([])
            setSummary(null)
          }, 3000)
        }
      } catch (err: any) {
        // All files failed
        setUploads((prev) =>
          prev.map((u) => ({
            ...u,
            status: 'error' as const,
            error: u.error || err.message,
          }))
        )
        setSummary({ success: 0, failed: files.length })
      } finally {
        setIsUploading(false)
      }
    },
    [folderId, onUploadComplete, onFilesSelected]
  )

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      // Mark first file as uploading immediately
      if (acceptedFiles.length > 0) {
        doUpload(acceptedFiles)
      }
    },
    [doUpload]
  )

  const handleFolderUpload = useCallback(() => {
    folderInputRef.current?.click()
  }, [])

  const handleFolderInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files && files.length > 0) {
        doUpload(Array.from(files))
      }
      // Reset input so the same folder can be re-selected
      e.target.value = ''
    },
    [doUpload]
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
          isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {isDragActive ? 'Drop files here' : 'Drop files or click to upload'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Hidden folder input */}
      <input
        ref={folderInputRef}
        type="file"
        className="hidden"
        onChange={handleFolderInputChange}
        /* @ts-expect-error webkitdirectory is non-standard but widely supported */
        webkitdirectory=""
        multiple
      />

      <div className="flex gap-3">
        {/* File drop zone */}
        <div
          {...getRootProps()}
          className={`flex-1 border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-950'
              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'
          } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
        >
          <input {...getInputProps()} />
          <div className="text-4xl mb-2">{'\uD83D\uDCC1'}</div>
          <p className="text-gray-700 dark:text-gray-300 font-medium">
            {isDragActive ? 'Drop files here...' : 'Drag & drop files here'}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            or click to select files (max {formatFileSize(MAX_FILE_SIZE)} each)
          </p>
        </div>

        {/* Folder upload button */}
        <button
          onClick={handleFolderUpload}
          disabled={isUploading}
          className={`flex flex-col items-center justify-center gap-2 w-40 border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors ${
            isUploading
              ? 'opacity-50 pointer-events-none border-gray-200 dark:border-gray-700'
              : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950'
          }`}
        >
          <FolderUp className="h-8 w-8 text-gray-400 dark:text-gray-500" />
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Upload Folder</span>
        </button>
      </div>

      {/* Upload progress */}
      {uploads.length > 0 && (
        <div className="space-y-1.5">
          {/* Summary bar */}
          {summary && (
            <div className={`text-sm font-medium px-3 py-1.5 rounded-md ${
              summary.failed === 0
                ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400'
                : summary.success === 0
                  ? 'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400'
                  : 'bg-yellow-50 dark:bg-yellow-950 text-yellow-700 dark:text-yellow-400'
            }`}>
              {summary.failed === 0
                ? `${summary.success} file${summary.success > 1 ? 's' : ''} uploaded successfully`
                : summary.success === 0
                  ? `All ${summary.failed} upload${summary.failed > 1 ? 's' : ''} failed`
                  : `${summary.success} uploaded, ${summary.failed} failed`}
            </div>
          )}

          {/* Individual file statuses */}
          {uploads.map((u, i) => (
            <div
              key={i}
              className="flex items-center gap-3 px-3 py-1.5 bg-white dark:bg-gray-900 border rounded-md text-sm"
            >
              <span className="flex-1 truncate text-gray-700 dark:text-gray-300">{u.file.name}</span>
              <span className="text-gray-400 dark:text-gray-500 shrink-0">{formatFileSize(u.file.size)}</span>
              {u.status === 'pending' && (
                <span className="text-gray-400 dark:text-gray-500 shrink-0">Waiting...</span>
              )}
              {u.status === 'uploading' && (
                <span className="text-blue-600 dark:text-blue-400 shrink-0">Uploading...</span>
              )}
              {u.status === 'done' && (
                <span className="text-green-600 dark:text-green-400 shrink-0">Done</span>
              )}
              {u.status === 'error' && (
                <span className="text-red-600 dark:text-red-400 shrink-0" title={u.error}>
                  Failed{u.error ? `: ${u.error}` : ''}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
