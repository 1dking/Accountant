import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createShareLink } from '@/api/public'
import { X, Copy, Check, Loader2, Link } from 'lucide-react'

interface ShareLinkDialogProps {
  isOpen: boolean
  resourceType: 'estimate' | 'invoice'
  resourceId: string
  onClose: () => void
}

export default function ShareLinkDialog({
  isOpen,
  resourceType,
  resourceId,
  onClose,
}: ShareLinkDialogProps) {
  const [copied, setCopied] = useState(false)
  const [shareUrl, setShareUrl] = useState('')

  const hasFired = useRef(false)

  const createMutation = useMutation({
    mutationFn: () => createShareLink(resourceType, resourceId),
    onSuccess: (response) => {
      const token = response.data.token
      const url = `${window.location.origin}/p/${token}`
      setShareUrl(url)
    },
  })

  // Auto-create link when dialog opens
  useEffect(() => {
    if (isOpen && !shareUrl && !hasFired.current) {
      hasFired.current = true
      createMutation.mutate()
    }
    if (!isOpen) {
      hasFired.current = false
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const input = document.querySelector<HTMLInputElement>('#share-url-input')
      if (input) {
        input.select()
        document.execCommand('copy')
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }
    }
  }

  const handleClose = () => {
    setShareUrl('')
    setCopied(false)
    createMutation.reset()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Link className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Share Link</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 rounded"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4">
          {createMutation.isPending && (
            <div className="flex items-center gap-3 py-4">
              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Creating shareable link...</span>
            </div>
          )}

          {createMutation.isError && (
            <div className="py-4">
              <p className="text-sm text-red-600">
                Failed to create share link. Please try again.
              </p>
              <button
                onClick={() => createMutation.mutate()}
                className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                Retry
              </button>
            </div>
          )}

          {shareUrl && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Anyone with this link can view this {resourceType}:
              </p>
              <div className="flex gap-2">
                <input
                  id="share-url-input"
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="flex-1 px-3 py-2 text-sm border rounded-md bg-gray-50 dark:bg-gray-950 text-gray-700 dark:text-gray-300 select-all"
                />
                <button
                  onClick={handleCopy}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                    copied
                      ? 'bg-green-100 text-green-700'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {copied ? (
                    <>
                      <Check className="h-4 w-4" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end px-6 py-4 border-t">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
