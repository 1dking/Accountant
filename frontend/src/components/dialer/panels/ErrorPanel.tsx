import { AlertCircle } from 'lucide-react'

export default function ErrorPanel({
  message,
  onRetry,
}: {
  message: string | null
  onRetry: () => void
}) {
  return (
    <div className="px-6 py-8 space-y-3 text-center">
      <AlertCircle className="h-8 w-8 mx-auto text-red-400" />
      <div>
        <div className="text-sm font-medium text-[color:var(--lg-text-primary)] mb-1">
          Dialer unavailable
        </div>
        <div
          className="text-xs text-[color:var(--lg-text-secondary)] break-words"
          title={message || undefined}
        >
          {message || 'Failed to initialize voice'}
        </div>
      </div>
      <button
        onClick={onRetry}
        className="w-full h-10 rounded-xl bg-blue-600/90 text-white text-sm font-medium hover:bg-blue-600 transition-colors"
      >
        Retry
      </button>
    </div>
  )
}
