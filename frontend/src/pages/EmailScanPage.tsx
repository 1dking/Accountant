import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Inbox, Search, Download, RefreshCw, FileText, CheckCircle } from 'lucide-react'
import {
  listGmailAccounts,
  listGmailScanResults,
  scanGmailEmails,
  importGmailAttachment,
} from '@/api/integrations'
import { formatDate } from '@/lib/utils'
import type { GmailScanResult } from '@/types/models'

export default function EmailScanPage() {
  const queryClient = useQueryClient()
  const [selectedAccount, setSelectedAccount] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('has:attachment (invoice OR receipt OR payment)')

  const { data: accountsData } = useQuery({
    queryKey: ['gmail-accounts'],
    queryFn: listGmailAccounts,
  })

  const { data: resultsData, isLoading: resultsLoading } = useQuery({
    queryKey: ['gmail-results', selectedAccount],
    queryFn: () => listGmailScanResults(selectedAccount || undefined),
  })

  const scanMutation = useMutation({
    mutationFn: () => scanGmailEmails({
      gmail_account_id: selectedAccount,
      query: searchQuery,
      max_results: 50,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
    },
  })

  const importMutation = useMutation({
    mutationFn: importGmailAttachment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
    },
  })

  const accounts = accountsData?.data ?? []
  const results: GmailScanResult[] = resultsData?.data ?? []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Email Scan</h1>
          <p className="text-gray-500 mt-1">Scan Gmail for invoices, receipts, and attachments</p>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.email}</option>
            ))}
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Gmail search query..."
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => scanMutation.mutate()}
            disabled={!selectedAccount || scanMutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${scanMutation.isPending ? 'animate-spin' : ''}`} />
            {scanMutation.isPending ? 'Scanning...' : 'Scan Now'}
          </button>
        </div>
        {!selectedAccount && accounts.length > 0 && (
          <p className="text-xs text-gray-400 mt-2">Select a Gmail account to start scanning.</p>
        )}
        {accounts.length === 0 && (
          <p className="text-xs text-amber-600 mt-2">
            No Gmail accounts connected. Go to Settings &gt; Gmail to connect one.
          </p>
        )}
      </div>

      {/* Results */}
      {resultsLoading ? (
        <p className="text-gray-400 py-8 text-center text-sm">Loading results...</p>
      ) : results.length > 0 ? (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Subject</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">From</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Date</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Attachments</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Status</th>
                <th className="text-right px-4 py-3 text-gray-500 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={result.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 truncate max-w-xs">
                      {result.subject || '(No subject)'}
                    </div>
                    {result.snippet && (
                      <div className="text-xs text-gray-400 truncate max-w-xs mt-0.5">
                        {result.snippet}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 truncate max-w-[180px]">
                    {result.sender || '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {result.date ? formatDate(result.date) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {result.has_attachments ? (
                      <span className="flex items-center gap-1 text-blue-600 text-xs">
                        <FileText className="w-3.5 h-3.5" /> Yes
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">No</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {result.is_processed ? (
                      <span className="flex items-center gap-1 text-xs text-green-600">
                        <CheckCircle className="w-3.5 h-3.5" /> Imported
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {result.has_attachments && !result.is_processed && (
                      <button
                        onClick={() => importMutation.mutate(result.id)}
                        disabled={importMutation.isPending}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 ml-auto"
                      >
                        <Download className="w-3 h-3" />
                        Import
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-16 bg-white border rounded-lg">
          <Inbox className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No scan results yet.</p>
          <p className="text-gray-400 text-sm mt-1">
            Select a Gmail account and click "Scan Now" to search for invoices and receipts.
          </p>
        </div>
      )}
    </div>
  )
}
