import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usePlaidLink, type PlaidLinkOnSuccess } from 'react-plaid-link'
import { Landmark, Trash2, RefreshCw, Save } from 'lucide-react'
import {
  listPlaidConnections, deletePlaidConnection, syncPlaidTransactions,
  getIntegrationSettings, saveIntegrationSettings,
  getPlaidLinkConfig, createPlaidLinkToken, exchangePlaidToken, type PlaidLinkConfig,
} from '@/api/integrations'
import { formatDate } from '@/lib/utils'

/** "Connect a bank" — rendered ONLY when the server says this user may (an
 *  allow-listed operator, MFA satisfied, flag on). Gating on the server's
 *  `enabled` (never on user role) is what keeps tenant admins out. */
function ConnectBank({ config }: { config: PlaidLinkConfig }) {
  const queryClient = useQueryClient()
  const [consent, setConsent] = useState(false)
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [status, setStatus] = useState('')

  const startMutation = useMutation({
    mutationFn: createPlaidLinkToken,
    onSuccess: (res) => setLinkToken(res.data.link_token),
    onError: () => setStatus('Could not start the bank connection. Please try again.'),
  })

  const exchangeMutation = useMutation({
    mutationFn: exchangePlaidToken,
    onSuccess: () => {
      setStatus('Bank connected.')
      setLinkToken(null)
      setConsent(false)
      queryClient.invalidateQueries({ queryKey: ['plaid-connections'] })
    },
    onError: () => setStatus('We could not finish connecting the bank. Please try again.'),
  })

  const onSuccess = useCallback<PlaidLinkOnSuccess>(
    (public_token, metadata) => {
      if (!public_token) return
      exchangeMutation.mutate({
        public_token,
        institution_name: metadata.institution?.name ?? 'Bank',
        institution_id: metadata.institution?.institution_id ?? '',
        consent_acknowledged: true,
      })
    },
    [exchangeMutation],
  )

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit: () => setLinkToken(null),
  })

  // Open Plaid's UI once the freshly-fetched link token has initialised.
  useEffect(() => {
    if (linkToken && ready) open()
  }, [linkToken, ready, open])

  const busy = startMutation.isPending || exchangeMutation.isPending

  return (
    <div className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Landmark className="w-4 h-4 text-blue-500" />
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Connect a bank</h3>
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 max-h-32 overflow-y-auto border rounded-md p-3 whitespace-pre-line">
        {config.consent_text}
      </div>
      <label className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          I have read and agree to the{' '}
          <a href={config.privacy_policy_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">Privacy Policy</a>
          {' '}and{' '}
          <a href={config.terms_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">Terms</a>, and consent to connecting my bank via Plaid.
        </span>
      </label>
      <button
        onClick={() => { setStatus(''); startMutation.mutate() }}
        disabled={!consent || busy}
        className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        <Landmark className="w-4 h-4" />
        {busy ? 'Connecting…' : 'Connect a bank'}
      </button>
      {status && <p className="text-xs text-gray-500 dark:text-gray-400">{status}</p>}
    </div>
  )
}

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

  // Server-authoritative gate for the "Connect a bank" button.
  const { data: linkConfigData } = useQuery({
    queryKey: ['plaid-link-config'],
    queryFn: getPlaidLinkConfig,
  })
  const linkConfig = linkConfigData?.data

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
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Bank Connections</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Connect bank accounts via Plaid to auto-import transactions.
          </p>
        </div>
      </div>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Plaid Config Form */}
      <form
        onSubmit={(e) => { e.preventDefault(); saveMutation.mutate() }}
        className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Plaid Configuration</h3>
          {isConfigured && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Configured</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client ID</label>
            <input
              type="text"
              value={configForm.client_id}
              onFocus={() => setConfigForm((f) => (f.client_id.startsWith('****') ? { ...f, client_id: '' } : f))}
              onChange={(e) => setConfigForm({ ...configForm, client_id: e.target.value })}
              placeholder={isConfigured ? 'Leave blank to keep current' : 'Your Plaid client ID'}
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Secret</label>
            <input
              type="password"
              value={configForm.secret}
              onFocus={() => setConfigForm((f) => (f.secret.startsWith('****') ? { ...f, secret: '' } : f))}
              onChange={(e) => setConfigForm({ ...configForm, secret: e.target.value })}
              placeholder={isConfigured ? 'Leave blank to keep current' : 'Your Plaid secret'}
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Environment</label>
            <select
              value={configForm.environment}
              onChange={(e) => setConfigForm({ ...configForm, environment: e.target.value })}
              className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="sandbox">Sandbox</option>
              <option value="production">Production</option>
            </select>
          </div>
        </div>
        {isConfigured && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Saved keys are hidden. Click a field to replace it — leave a field blank to keep the
            current key. Switching <span className="font-medium">Environment</span>? Re-enter{' '}
            <span className="font-medium">both</span> keys for that environment.
          </p>
        )}
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
        </button>
      </form>

      {/* Connect a bank — only when the server authorises THIS user (operator
          allow-list + MFA + flag). Hidden for everyone else. */}
      {linkConfig?.enabled && <ConnectBank config={linkConfig} />}

      {/* Connections */}
      <div className="space-y-3">
        {connections.map((conn) => (
          <div key={conn.id} className="bg-white dark:bg-gray-900 border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Landmark className="w-4 h-4 text-blue-500" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">{conn.institution_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${conn.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}`}>
                    {conn.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Last synced: {conn.last_sync_at ? formatDate(conn.last_sync_at) : 'Never'}
                </p>
                {conn.accounts && conn.accounts.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {conn.accounts.map((acct) => (
                      <span key={acct.account_id} className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 px-2 py-1 rounded">
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
                  className="flex items-center gap-1 px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
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
          <div className="text-center py-12 bg-white dark:bg-gray-900 border rounded-lg">
            <Landmark className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 text-sm">No bank accounts connected.</p>
            <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
              Configure your Plaid credentials above, then connect a bank account.
            </p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How it works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Securely connect bank accounts through Plaid</li>
          <li>Transactions are synced automatically every 4 hours</li>
          <li>Categorize transactions as expenses or income</li>
          <li>Match transactions to existing invoices</li>
        </ul>
        <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
          Two-factor authentication and your explicit consent are required before you can connect a
          bank account. Read our{' '}
          <a
            href="/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Privacy Policy
          </a>{' '}
          to see how bank data is used.
        </p>
      </div>
    </div>
  )
}
