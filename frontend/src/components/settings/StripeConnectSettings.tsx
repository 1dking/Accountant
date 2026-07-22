import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Trash2 } from 'lucide-react'
import { connectStripeAccount, getStripeConnectStatus, disconnectStripeAccount } from '@/api/integrations'
import { ApiClientError } from '@/api/client'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'

export default function StripeConnectSettings() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const handledRef = useRef(false)

  useEffect(() => {
    if (handledRef.current) return
    const connected = searchParams.get('connected')
    const pending = searchParams.get('pending')
    const error = searchParams.get('error')
    if (connected === 'true') {
      handledRef.current = true
      toast.success('Stripe account connected!')
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    } else if (pending === 'true') {
      handledRef.current = true
      toast('Stripe onboarding started — finish it in Stripe to start accepting payments.')
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    } else if (error) {
      handledRef.current = true
      toast.error(`Stripe connection failed: ${decodeURIComponent(error)}`)
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    }
  }, [searchParams, queryClient, setSearchParams])

  const { data, isLoading } = useQuery({
    queryKey: ['stripe-connect-status'],
    queryFn: getStripeConnectStatus,
  })

  const connectMutation = useMutation({
    mutationFn: connectStripeAccount,
    onSuccess: (data) => {
      window.location.href = data.data.url
    },
    onError: (err: unknown) => {
      const message = err instanceof ApiClientError ? err.error.message : 'Failed to start Stripe onboarding'
      toast.error(message)
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: disconnectStripeAccount,
    onSuccess: () => {
      toast.success('Stripe account disconnected')
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
    },
  })

  const account = data?.data ?? null

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Stripe Connect</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Connect your own Stripe account so invoice and proposal payments from your clients land directly in your balance.
        </p>
      </div>

      {!isLoading && !account && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-6 text-center">
          <CreditCard className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">
            No Stripe account connected yet.
          </p>
          <button
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <CreditCard className="w-4 h-4" />
            {connectMutation.isPending ? 'Connecting...' : 'Connect Stripe Account'}
          </button>
        </div>
      )}

      {account && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-500" />
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {account.stripe_account_id}
                </span>
                {account.charges_enabled ? (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                    Active — accepting payments
                  </span>
                ) : (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                    Onboarding incomplete
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {account.onboarding_completed_at
                  ? `Live since ${formatDate(account.onboarding_completed_at)}`
                  : 'Finish onboarding in Stripe to start accepting payments.'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!account.charges_enabled && (
                <button
                  onClick={() => connectMutation.mutate()}
                  disabled={connectMutation.isPending}
                  className="flex items-center gap-1 px-2 py-1 text-sm text-blue-600 border border-blue-200 rounded hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50"
                >
                  Continue onboarding
                </button>
              )}
              <button
                onClick={() => { if (confirm('Disconnect your Stripe account? Client payments will stop routing to it until you reconnect.')) disconnectMutation.mutate() }}
                className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 dark:hover:bg-red-950"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Disconnect
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How it works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Connect a Stripe Express account through Stripe's own onboarding flow</li>
          <li>Once active, invoice and proposal payment links route to your account</li>
          <li>Without a connected account, payments fall back to the platform default</li>
        </ul>
      </div>
    </div>
  )
}
