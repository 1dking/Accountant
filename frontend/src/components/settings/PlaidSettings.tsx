import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Landmark, Trash2, RefreshCw, Save } from 'lucide-react'
import { listPlaidConnections, deletePlaidConnection, syncPlaidTransactions, getIntegrationSettings, saveIntegrationSettings } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

export default function PlaidSettings() {
  const queryClient = useQueryClient()
  const [msg, setMsg] = useState('')

  // Config form
  const [configForm, setConfigForm] = useState({
    client_id: '',
    secret: '',
    environment: 'sandbox',
  })
  const [configLoaded, setConfigLoaded] = useState(false)

  const { data: settingsData } = useQuery({
    queryKey: ['integration-settings', 'plaid'],
    queryFn: () => getIntegrationSettings('plaid'),
  })

  if (settingsData && !configLoaded) {
    setConfigForm({
      client_id: settingsData.data?.client_id || '',
      secret: settingsData.data?.secret || '',
      environment: settingsData.data?.environment || 'sandbox',
    })
    setConfigLoaded(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => saveIntegrationSettings('plaid', configForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-settings', 'plaid'] })
      setConfigLoaded(false)
      setMsg('Plaid settings saved!')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg('Failed to save settings')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const { data } = useQuery({
    queryKey: ['plaid-connections'],
    queryFn: listPlaidConnections,
  })

  const deleteMutation = useMutation({
    mutationFn: deletePlaidConnection,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-connections'] }),
  })

  const syncMutation = useMutation({
    mutationFn: syncPlaidTransactions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plaid-connections'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
    },
  })

  const connections = data?.data ?? []
  const isConfigured = settingsData?.meta?.is_configured ?? false

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Bank Connections</h2>
          <p className="text-sm text-gray-500 mt-1">
            Connect bank accounts via Plaid to auto-import transactions.
          </p>
        </div>
      </div>

      {msg && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Plaid Config Form */}
      <form
        onSubmit={(e) => { e.preventDefault(); saveMutation.mutate() }}
        className="bg-white border rounded-lg p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700">Plaid Configuration</h3>
          {isConfigured && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Configured</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
            <input
              type="text"
              value={configForm.client_id}
              onChange={(e) => setConfigForm({ ...configForm, client_id: e.target.value })}
              placeholder="Your Plaid client ID"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Secret</label>
            <input
              type="password"
              value={configForm.secret}
              onChange={(e) => setConfigForm({ ...configForm, secret: e.target.value })}
              placeholder="Your Plaid secret"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Environment</label>
            <select
              value={configForm.environment}
              onChange={(e) => setConfigForm({ ...configForm, environment: e.target.value })}
              className="w-full px-3 py-2 border rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="sandbox">Sandbox</option>
              <option value="development">Development</option>
              <option value="production">Production</option>
            </select>
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

      {/* Connections */}
      <div className="space-y-3">
        {connections.map((conn) => (
          <div key={conn.id} className="bg-white border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Landmark className="w-4 h-4 text-blue-500" />
                  <span className="font-medium text-gray-900">{conn.institution_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${conn.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {conn.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  Last synced: {conn.last_sync_at ? formatDate(conn.last_sync_at) : 'Never'}
                </p>
                {conn.accounts && conn.accounts.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {conn.accounts.map((acct) => (
                      <span key={acct.account_id} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                        {acct.name} {acct.mask ? `••${acct.mask}` : ''}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => syncMutation.mutate(conn.id)}
                  disabled={syncMutation.isPending}
                  className="flex items-center gap-1 px-2 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                  Sync
                </button>
                <button
                  onClick={() => { if (confirm(`Disconnect ${conn.institution_name}?`)) deleteMutation.mutate(conn.id) }}
                  className="p-1 text-red-500 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {connections.length === 0 && (
          <div className="text-center py-12 bg-white border rounded-lg">
            <Landmark className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">No bank accounts connected.</p>
            <p className="text-gray-400 text-xs mt-1">
              Configure your Plaid credentials above, then connect a bank account.
            </p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-600">
        <h4 className="font-medium text-gray-700 mb-1">How it works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500">
          <li>Securely connect bank accounts through Plaid</li>
          <li>Transactions are synced automatically every 4 hours</li>
          <li>Categorize transactions as expenses or income</li>
          <li>Match transactions to existing invoices</li>
        </ul>
      </div>
    </div>
  )
}
