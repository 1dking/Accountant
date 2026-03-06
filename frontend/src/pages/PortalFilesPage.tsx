import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getPortalFiles } from '../api/portal'
import { api } from '../api/client'

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIcon(mimeType: string): string {
  if (mimeType.startsWith('image/')) return 'Image'
  if (mimeType === 'application/pdf') return 'PDF'
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) return 'Spreadsheet'
  if (mimeType.includes('document') || mimeType.includes('word')) return 'Document'
  return 'File'
}

export default function PortalFilesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'files'],
    queryFn: getPortalFiles,
  })

  const files = data?.data ?? []

  async function handleDownload(fileId: string, filename: string) {
    try {
      const blob = await api.download(`/portal/files/${fileId}/download`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      // Download failed silently
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">Shared Files</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/portal" className="text-muted-foreground hover:text-foreground">Dashboard</Link>
            <Link to="/portal/invoices" className="text-muted-foreground hover:text-foreground">Invoices</Link>
            <Link to="/portal/proposals" className="text-muted-foreground hover:text-foreground">Proposals</Link>
            <Link to="/portal/files" className="font-medium text-foreground">Files</Link>
            <Link to="/portal/meetings" className="text-muted-foreground hover:text-foreground">Meetings</Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto">
        {isLoading ? (
          <p className="text-muted-foreground">Loading files...</p>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No files have been shared with you.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {files.map((file) => (
              <div key={file.share_id} className="border rounded-lg p-4 hover:bg-muted/30 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    {fileIcon(file.mime_type)}
                  </span>
                  <span className="text-xs text-muted-foreground capitalize">{file.permission}</span>
                </div>
                <h3 className="font-medium text-sm truncate mb-1" title={file.filename}>
                  {file.filename}
                </h3>
                <p className="text-xs text-muted-foreground mb-3">
                  {formatFileSize(file.file_size)} -- Shared {new Date(file.shared_at).toLocaleDateString()}
                </p>
                {file.permission === 'download' ? (
                  <button
                    onClick={() => handleDownload(file.file_id, file.filename)}
                    className="w-full px-3 py-1.5 text-xs font-medium border rounded hover:bg-accent transition-colors"
                  >
                    Download
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">View only</span>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
