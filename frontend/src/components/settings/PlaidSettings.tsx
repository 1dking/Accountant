import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Landmark, Trash2, RefreshCw } from 'lucide-react'
import { listPlaidConnections, deletePlaidConnection, syncPlaidTransactions } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

export default function PlaidSettings() {
  const queryClient = useQueryClient()

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

  const handleConnect = async () => {
    // Plaid Link integration would go here
    // For now, show a message about configuring Plaid credentials
    alert('To connect a bank account, ensure PLAID_CLIENT_ID and PLAID_SECRET are set in your .env file, then Plaid Link will open here.')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Bank Connections</h2>
          <p className="text-sm text-gray-500 mt-1">
            Connect bank accounts via Plaid to auto-import transactions.
          </p>
        </div>
        <button
          onClick={handleConnect}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Landmark className="w-4 h-4" />
          Connect Bank
        </button>
      </div>

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
              Connect a bank account to automatically import transactions.
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
          <li>Running in sandbox mode for testing</li>
        </ul>
      </div>
    </div>
  )
}
