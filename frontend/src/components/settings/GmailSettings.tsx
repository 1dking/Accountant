import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, Trash2, ExternalLink } from 'lucide-react'
import { connectGmail, listGmailAccounts, disconnectGmailAccount } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

export default function GmailSettings() {
  const queryClient = useQueryClient()

  const { data } = useQuery({
    queryKey: ['gmail-accounts'],
    queryFn: listGmailAccounts,
  })

  const connectMutation = useMutation({
    mutationFn: connectGmail,
    onSuccess: (data) => {
      const authUrl = data.data.auth_url
      window.location.href = authUrl
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: disconnectGmailAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['gmail-accounts'] }),
  })

  const accounts = data?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Gmail Integration</h2>
          <p className="text-sm text-gray-500 mt-1">
            Connect Gmail accounts to scan for invoices, receipts, and send emails.
          </p>
        </div>
        <button
          onClick={() => connectMutation.mutate()}
          disabled={connectMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Mail className="w-4 h-4" />
          {connectMutation.isPending ? 'Connecting...' : 'Connect Gmail'}
        </button>
      </div>

      <div className="space-y-3">
        {accounts.map((account) => (
          <div key={account.id} className="bg-white border rounded-lg p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-red-500" />
                <span className="font-medium text-gray-900">{account.email}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${account.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {account.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Last synced: {account.last_sync_at ? formatDate(account.last_sync_at) : 'Never'}
              </p>
            </div>
            <button
              onClick={() => { if (confirm(`Disconnect ${account.email}?`)) disconnectMutation.mutate(account.id) }}
              className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Disconnect
            </button>
          </div>
        ))}

        {accounts.length === 0 && (
          <div className="text-center py-12 bg-white border rounded-lg">
            <Mail className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">No Gmail accounts connected.</p>
            <p className="text-gray-400 text-xs mt-1">
              Connect a Gmail account to scan emails for invoices and receipts.
            </p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-600">
        <h4 className="font-medium text-gray-700 mb-1">How it works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500">
          <li>Connect your Gmail accounts via Google OAuth</li>
          <li>We scan for emails matching invoices, receipts, and payments</li>
          <li>Import attachments directly as documents</li>
          <li>Send emails through connected Gmail accounts</li>
          <li>Auto-scan runs every 30 minutes</li>
        </ul>
      </div>
    </div>
  )
}
