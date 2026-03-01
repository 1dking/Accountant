import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Trash2, Save } from 'lucide-react'
import { listStripeSubscriptions, cancelStripeSubscription, getIntegrationSettings, saveIntegrationSettings } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  cancelled: 'bg-gray-100 dark:bg-gray-800 text-gray-600',
  past_due: 'bg-red-100 text-red-700',
  incomplete: 'bg-yellow-100 text-yellow-700',
}

export default function StripeSettings() {
  const queryClient = useQueryClient()
  const [msg, setMsg] = useState('')

  // Config form
  const [configForm, setConfigForm] = useState({
    secret_key: '',
    publishable_key: '',
    webhook_secret: '',
  })
  const [configLoaded, setConfigLoaded] = useState(false)

  const { data: settingsData } = useQuery({
    queryKey: ['integration-settings', 'stripe'],
    queryFn: () => getIntegrationSettings('stripe'),
  })

  if (settingsData && !configLoaded) {
    setConfigForm({
      secret_key: settingsData.data?.secret_key || '',
      publishable_key: settingsData.data?.publishable_key || '',
      webhook_secret: settingsData.data?.webhook_secret || '',
    })
    setConfigLoaded(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => saveIntegrationSettings('stripe', configForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-settings', 'stripe'] })
      queryClient.invalidateQueries({ queryKey: ['stripe-config'] })
      setConfigLoaded(false)
      setMsg('Stripe settings saved!')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg('Failed to save settings')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const { data: subsData } = useQuery({
    queryKey: ['stripe-subscriptions'],
    queryFn: listStripeSubscriptions,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelStripeSubscription,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stripe-subscriptions'] }),
  })

  const subscriptions = subsData?.data ?? []
  const isConfigured = settingsData?.meta?.is_configured ?? false

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Stripe Payments</h2>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Stripe Config Form */}
      <form
        onSubmit={(e) => { e.preventDefault(); saveMutation.mutate() }}
        className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Stripe Configuration</h3>
          {isConfigured && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Configured</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Secret Key</label>
            <input
              type="password"
              value={configForm.secret_key}
              onChange={(e) => setConfigForm({ ...configForm, secret_key: e.target.value })}
              placeholder="sk_live_..."
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Publishable Key</label>
            <input
              type="text"
              value={configForm.publishable_key}
              onChange={(e) => setConfigForm({ ...configForm, publishable_key: e.target.value })}
              placeholder="pk_live_..."
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Webhook Secret</label>
            <input
              type="password"
              value={configForm.webhook_secret}
              onChange={(e) => setConfigForm({ ...configForm, webhook_secret: e.target.value })}
              placeholder="whsec_..."
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
        </button>
      </form>

      {/* Subscriptions */}
      {subscriptions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Active Subscriptions</h3>
          <div className="space-y-3">
            {subscriptions.map((sub) => (
              <div key={sub.id} className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-purple-500" />
                    <span className="font-medium text-gray-900 dark:text-gray-100">{sub.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[sub.status] || 'bg-gray-100 dark:bg-gray-800 text-gray-600'}`}>
                      {sub.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
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

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Features</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Generate payment links for invoices (one-time payments)</li>
          <li>Create recurring subscriptions for clients</li>
          <li>Automatic payment recording via webhooks</li>
          <li>Invoice status auto-updates when paid</li>
        </ul>
      </div>
    </div>
  )
}
