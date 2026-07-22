import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Loader2, AlertCircle } from 'lucide-react'
import { createCheckout } from '@/api/proposals'
import { ApiClientError } from '@/api/client'

export default function ProposalPaymentRedirectPage() {
  const { id } = useParams<{ id: string }>()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false

    createCheckout(id)
      .then((response) => {
        if (cancelled) return
        window.location.href = response.data.checkout_url
      })
      .catch((err) => {
        if (cancelled) return
        const message = err instanceof ApiClientError ? err.error.message : 'Failed to start checkout.'
        setError(message)
      })

    return () => {
      cancelled = true
    }
  }, [id])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <div className="max-w-sm w-full text-center">
        {error ? (
          <>
            <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Couldn't start payment
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">{error}</p>
          </>
        ) : (
          <>
            <Loader2 className="w-10 h-10 text-blue-600 mx-auto mb-4 animate-spin" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Taking you to secure checkout...
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Please wait a moment.</p>
          </>
        )}
      </div>
    </div>
  )
}
