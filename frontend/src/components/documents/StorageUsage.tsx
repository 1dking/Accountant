import { useQuery } from '@tanstack/react-query'
import { getStorageUsage } from '@/api/documents'
import { formatFileSize } from '@/lib/utils'
import { HardDrive } from 'lucide-react'

export default function StorageUsage() {
  const { data } = useQuery({
    queryKey: ['storage-usage'],
    queryFn: getStorageUsage,
  })

  const usage = data?.data
  if (!usage) return null

  const totalBytes = usage.total_bytes
  // Assume a reasonable storage limit for the visual bar (10 GB)
  const storageLimit = 10 * 1024 * 1024 * 1024
  const percentage = Math.min((totalBytes / storageLimit) * 100, 100)

  return (
    <div className="px-3 py-3 border-t border-gray-100 dark:border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <HardDrive className="h-4 w-4 text-gray-400 dark:text-gray-500" />
        <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Storage</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${
            percentage > 90 ? 'bg-red-500' : percentage > 70 ? 'bg-yellow-500' : 'bg-blue-500'
          }`}
          style={{ width: `${Math.max(percentage, 1)}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {formatFileSize(totalBytes)} used
      </p>
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
        {usage.document_count} files, {usage.folder_count} folders
      </p>
    </div>
  )
}
