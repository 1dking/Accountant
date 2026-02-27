import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Trash2, CheckCircle, XCircle } from 'lucide-react'
import { getStripeConfig, listStripeSubscriptions, cancelStripeSubscription } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-100 text-gray-600',
  past_due: 'bg-red-100 text-red-700',
  incomplete: 'bg-yellow-100 text-yellow-700',
}

export default function StripeSettings() {
  const queryClient = useQueryClient()

  const { data: configData } = useQuery({
    queryKey: ['stripe-config'],
    queryFn: getStripeConfig,
  })

  const { data: subsData } = useQuery({
    queryKey: ['stripe-subscriptions'],
    queryFn: listStripeSubscriptions,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelStripeSubscription,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stripe-subscriptions'] }),
  })

  const config = configData?.data
  const subscriptions = subsData?.data ?? []

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-gray-900">Stripe Payments</h2>

      {/* Status */}
      <div className="bg-white border rounded-lg p-4 flex items-center gap-3">
        {config?.is_configured ? (
          <>
            <CheckCircle className="w-5 h-5 text-green-500" />
            <div>
              <p className="font-medium text-gray-900">Stripe is configured</p>
              <p className="text-sm text-gray-500">Payment links and subscriptions are available.</p>
            </div>
          </>
        ) : (
          <>
            <XCircle className="w-5 h-5 text-gray-400" />
            <div>
              <p className="font-medium text-gray-900">Stripe is not configured</p>
              <p className="text-sm text-gray-500">
                Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY in your .env file.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Subscriptions */}
      {subscriptions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Active Subscriptions</h3>
          <div className="space-y-3">
            {subscriptions.map((sub) => (
              <div key={sub.id} className="bg-white border rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-purple-500" />
                    <span className="font-medium text-gray-900">{sub.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[sub.status] || 'bg-gray-100 text-gray-600'}`}>
                      {sub.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {formatCurrency(sub.amount, sub.currency)} / {sub.interval}
                    {sub.current_period_end && ` · Next billing: ${formatDate(sub.current_period_end)}`}
                  </p>
                </div>
                {sub.status === 'active' && (
                  <button
                    onClick={() => { if (confirm(`Cancel subscription "${sub.name}"?`)) cancelMutation.mutate(sub.id) }}
                    disabled={cancelMutation.isPending}
                    className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-600">
        <h4 className="font-medium text-gray-700 mb-1">Features</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500">
          <li>Generate payment links for invoices (one-time payments)</li>
          <li>Create recurring subscriptions for clients</li>
          <li>Automatic payment recording via webhooks</li>
          <li>Invoice status auto-updates when paid</li>
        </ul>
      </div>
    </div>
  )
}
