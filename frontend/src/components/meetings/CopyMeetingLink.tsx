/**
 * Reusable share-link panel for meetings (Commit 23).
 *
 * Shows the public /m/{slug} URL with a one-click copy button. Used
 * both in the meeting-detail page (large inline card) and inside the
 * host toolbar's Share popover (compact). Defaults to compact; pass
 * variant="card" for the larger inline form.
 */
import { useState } from 'react'
import { Copy, Check, Link as LinkIcon } from 'lucide-react'

export interface CopyMeetingLinkProps {
  slug: string
  variant?: 'compact' | 'card'
}

export function buildMeetingShareUrl(slug: string): string {
  return `${window.location.origin}/m/${slug}`
}

export async function copyMeetingShareUrl(slug: string): Promise<void> {
  const url = buildMeetingShareUrl(slug)
  try {
    await navigator.clipboard.writeText(url)
    return
  } catch {
    // Fallback for older browsers / missing clipboard permission.
    const t = document.createElement('textarea')
    t.value = url
    document.body.appendChild(t)
    t.select()
    try { document.execCommand('copy') } catch { /* ignore */ }
    document.body.removeChild(t)
  }
}

export default function CopyMeetingLink({ slug, variant = 'compact' }: CopyMeetingLinkProps) {
  const [copied, setCopied] = useState(false)
  const url = buildMeetingShareUrl(slug)

  const handleCopy = async () => {
    await copyMeetingShareUrl(slug)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  if (variant === 'card') {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-2">
          <LinkIcon className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-semibold text-gray-900">Share this meeting</span>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          Anyone with this link can knock. You'll admit them from the lobby.
        </p>
        <div className="flex gap-2">
          <input
            readOnly
            value={url}
            onClick={(e) => (e.target as HTMLInputElement).select()}
            className="flex-1 px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg text-gray-700 font-mono"
          />
          <button
            onClick={handleCopy}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white rounded-lg transition ${
              copied ? 'bg-emerald-600' : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copied' : 'Copy link'}
          </button>
        </div>
      </div>
    )
  }

  // Compact (inside toolbar Share popover).
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <input
        readOnly
        value={url}
        onClick={(e) => (e.target as HTMLInputElement).select()}
        style={{
          flex: 1, padding: '8px 10px', fontSize: 12,
          background: '#0f172a', color: 'white',
          border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
          outline: 'none',
        }}
      />
      <button
        onClick={handleCopy}
        style={{
          padding: '8px 12px', fontSize: 12, fontWeight: 600,
          background: copied ? '#16a34a' : '#4f46e5',
          color: 'white', border: 'none', borderRadius: 8,
          cursor: 'pointer', display: 'inline-flex',
          alignItems: 'center', gap: 5,
        }}
        title={copied ? 'Copied!' : 'Copy link'}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}
