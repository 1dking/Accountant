import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, Trash2, RefreshCw } from 'lucide-react'
import { connectGmail, listGmailAccounts, disconnectGmailAccount, scanGmailEmails } from '@/api/integrations'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'

export default function GmailSettings() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const handledRef = useRef(false)

  useEffect(() => {
    if (handledRef.current) return
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected === 'true') {
      handledRef.current = true
      toast.success('Gmail account connected successfully!')
      queryClient.invalidateQueries({ queryKey: ['gmail-accounts'] })
      setSearchParams({ tab: 'gmail' }, { replace: true })
    } else if (error) {
      handledRef.current = true
      toast.error(`Gmail connection failed: ${decodeURIComponent(error)}`)
      setSearchParams({ tab: 'gmail' }, { replace: true })
    }
  }, [searchParams, queryClient, setSearchParams])

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

  const syncMutation = useMutation({
    mutationFn: (accountId: string) => scanGmailEmails({ gmail_account_id: accountId, max_results: 50 }),
    onSuccess: (data) => {
      const count = data?.data?.length ?? 0
      toast.success(count > 0 ? `Found ${count} new email(s)` : 'No new emails found')
      queryClient.invalidateQueries({ queryKey: ['gmail-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Sync failed')
    },
  })

  const accounts = data?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Gmail Integration</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
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
          <div key={account.id} className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-red-500" />
                <span className="font-medium text-gray-900 dark:text-gray-100">{account.email}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${account.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}`}>
                  {account.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Last synced: {account.last_sync_at ? formatDate(account.last_sync_at) : 'Never'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => syncMutation.mutate(account.id)}
                disabled={syncMutation.isPending}
                className="flex items-center gap-1 px-2 py-1 text-sm text-blue-600 border border-blue-200 rounded hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
              </button>
              <button
                onClick={() => { if (confirm(`Disconnect ${account.email}?`)) disconnectMutation.mutate(account.id) }}
                className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 dark:hover:bg-red-950"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Disconnect
              </button>
            </div>
          </div>
        ))}

        {accounts.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-gray-900 border rounded-lg">
            <Mail className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 text-sm">No Gmail accounts connected.</p>
            <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
              Connect a Gmail account to scan emails for invoices and receipts.
            </p>
          </div>
        )}
      </div>

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How it works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
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
