import { AlertCircle } from 'lucide-react'

export default function PermissionDeniedPanel() {
  return (
    <div className="px-6 py-8 space-y-3 text-center">
      <AlertCircle className="h-8 w-8 mx-auto text-red-400" />
      <div>
        <div className="text-sm font-medium text-[color:var(--lg-text-primary)] mb-1">
          Microphone access denied
        </div>
        <div className="text-xs text-[color:var(--lg-text-secondary)]">
          Re-enable microphone permission in your browser settings (click the
          lock icon in the address bar) and reload this page.
        </div>
      </div>
    </div>
  )
}
