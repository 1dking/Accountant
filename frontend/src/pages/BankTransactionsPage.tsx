import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Landmark, RefreshCw, ArrowUpRight, ArrowDownRight, Check, Filter, Sparkles, ListChecks } from 'lucide-react'
import {
  listPlaidConnections,
  listPlaidTransactions,
  categorizePlaidTransaction,
  syncPlaidTransactions,
  applyCategorizationRules,
  aiCategorizeTransactions,
} from '@/api/integrations'
import { formatDate } from '@/lib/utils'
import type { PlaidTransaction } from '@/types/models'

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)

export default function BankTransactionsPage() {
  const queryClient = useQueryClient()
  const [connectionId, setConnectionId] = useState<string>('')
  const [filterCategorized, setFilterCategorized] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')
  const [page, setPage] = useState(1)

  const { data: connectionsData } = useQuery({
    queryKey: ['plaid-connections'],
    queryFn: listPlaidConnections,
  })

  const { data: txnData, isLoading } = useQuery({
    queryKey: ['plaid-transactions', connectionId, filterCategorized, filterType, page],
    queryFn: () => listPlaidTransactions({
      connection_id: connectionId || undefined,
      is_categorized: filterCategorized === '' ? undefined : filterCategorized === 'true',
      is_income: filterType === '' ? undefined : filterType === 'income',
      page,
      page_size: 50,
    }),
  })

  const syncMutation = useMutation({
    mutationFn: syncPlaidTransactions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['plaid-connections'] })
    },
  })

  const categorizeMutation = useMutation({
    mutationFn: ({ txnId, asType }: { txnId: string; asType: 'expense' | 'income' | 'ignore' }) =>
      categorizePlaidTransaction(txnId, { as_type: asType }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] }),
  })

  const applyRulesMutation = useMutation({
    mutationFn: applyCategorizationRules,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] }),
  })

  const aiCategorizeMutation = useMutation({
    mutationFn: aiCategorizeTransactions,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] }),
  })

  const connections = connectionsData?.data ?? []
  const transactions: PlaidTransaction[] = txnData?.data ?? []
  const meta = txnData?.meta ?? { total: 0, page: 1, page_size: 50 }
  const totalPages = Math.ceil(meta.total / meta.page_size)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bank Transactions</h1>
          <p className="text-gray-500 mt-1">
            View and categorize transactions from connected bank accounts
          </p>
        </div>
        {connections.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => applyRulesMutation.mutate()}
              disabled={applyRulesMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <ListChecks className="w-4 h-4" />
              {applyRulesMutation.isPending ? 'Applying...' : 'Apply Rules'}
            </button>
            <button
              onClick={() => aiCategorizeMutation.mutate()}
              disabled={aiCategorizeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-purple-300 text-purple-700 rounded-lg hover:bg-purple-50 disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${aiCategorizeMutation.isPending ? 'animate-pulse' : ''}`} />
              {aiCategorizeMutation.isPending ? 'Categorizing...' : 'AI Categorize'}
            </button>
            <button
              onClick={() => {
                if (connectionId) syncMutation.mutate(connectionId)
                else connections.forEach((c) => syncMutation.mutate(c.id))
              }}
              disabled={syncMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
              Sync
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white border rounded-lg p-4 flex flex-wrap gap-3 items-center">
        <Filter className="w-4 h-4 text-gray-400" />
        <select
          value={connectionId}
          onChange={(e) => { setConnectionId(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All banks</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>{c.institution_name}</option>
          ))}
        </select>
        <select
          value={filterCategorized}
          onChange={(e) => { setFilterCategorized(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All status</option>
          <option value="false">Uncategorized</option>
          <option value="true">Categorized</option>
        </select>
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
          className="px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All types</option>
          <option value="expense">Expenses</option>
          <option value="income">Income</option>
        </select>
        <span className="text-sm text-gray-400 ml-auto">
          {meta.total} transaction{meta.total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Transactions */}
      {isLoading ? (
        <p className="text-gray-400 py-8 text-center text-sm">Loading transactions...</p>
      ) : transactions.length > 0 ? (
        <>
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Date</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Description</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Category</th>
                  <th className="text-right px-4 py-3 text-gray-500 font-medium">Amount</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium">Status</th>
                  <th className="text-right px-4 py-3 text-gray-500 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{formatDate(txn.date)}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{txn.merchant_name || txn.name}</div>
                      {txn.merchant_name && txn.name !== txn.merchant_name && (
                        <div className="text-xs text-gray-400">{txn.name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{txn.category || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`flex items-center justify-end gap-1 font-medium ${txn.is_income ? 'text-green-600' : 'text-gray-900'}`}>
                        {txn.is_income ? <ArrowDownRight className="w-3.5 h-3.5" /> : <ArrowUpRight className="w-3.5 h-3.5" />}
                        {formatCurrency(txn.amount)}
                      </span>
                      {txn.pending && <span className="text-xs text-amber-500">Pending</span>}
                    </td>
                    <td className="px-4 py-3">
                      {txn.is_categorized ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <Check className="w-3.5 h-3.5" />
                          {txn.matched_expense_id ? 'Expense' : txn.matched_income_id ? 'Income' : 'Ignored'}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">Uncategorized</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!txn.is_categorized && (
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => categorizeMutation.mutate({ txnId: txn.id, asType: 'expense' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-red-50 text-red-600 border-red-200"
                          >
                            Expense
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txnId: txn.id, asType: 'income' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-green-50 text-green-600 border-green-200"
                          >
                            Income
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txnId: txn.id, asType: 'ignore' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-gray-50 text-gray-500"
                          >
                            Ignore
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      ) : connections.length === 0 ? (
        <div className="text-center py-16 bg-white border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No bank accounts connected.</p>
          <p className="text-gray-400 text-sm mt-1">
            Go to Settings &gt; Banking to connect a bank account.
          </p>
        </div>
      ) : (
        <div className="text-center py-16 bg-white border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No transactions found.</p>
          <p className="text-gray-400 text-sm mt-1">
            Click "Sync" to import transactions from your bank.
          </p>
        </div>
      )}
    </div>
  )
}
