import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Landmark, RefreshCw, ArrowUpRight, ArrowDownRight, Check, Filter, Sparkles, ListChecks, AlertTriangle } from 'lucide-react'
import {
  listPlaidConnections,
  listPlaidTransactions,
  categorizePlaidTransaction,
  syncPlaidTransactions,
  applyCategorizationRules,
  aiCategorizeTransactions,
  getPlaidPossibleDuplicates,
} from '@/api/integrations'
import { ApiClientError } from '@/api/client'
import { formatDate } from '@/lib/utils'
import type { PlaidTransaction } from '@/types/models'

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)

/** Shown when categorizing a Plaid txn returns 409 PLAID_POSSIBLE_DUPLICATE.
 *  Puts the bank transaction next to the matching manual entry so the user
 *  decides: same transaction (skip, post nothing) or a separate charge (add). */
export function DuplicateDialog({ txn, asType, onSkip, onConfirm, confirming }: {
  txn: PlaidTransaction
  asType: 'expense' | 'income'
  onSkip: () => void
  onConfirm: () => void
  confirming: boolean
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['plaid-possible-duplicates', txn.id],
    queryFn: () => getPlaidPossibleDuplicates(txn.id),
  })
  const candidates = data?.data?.possible_duplicates ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onSkip}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Possible duplicate</h3>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          This bank transaction looks like one you already recorded by hand. Adding it as
          a new {asType} would count it twice.
        </p>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="border rounded-lg p-3">
            <div className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">From your bank</div>
            <div className="font-medium text-gray-900 dark:text-gray-100">{txn.merchant_name || txn.name}</div>
            <div className="text-sm text-gray-500 dark:text-gray-400">{formatDate(txn.date)}</div>
            <div className="text-sm font-semibold mt-1">{formatCurrency(txn.amount)}</div>
          </div>
          <div className="border border-amber-200 dark:border-amber-800 rounded-lg p-3 bg-amber-50 dark:bg-amber-900/20">
            <div className="text-[11px] uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-1">Already in your books</div>
            {isLoading ? (
              <div className="text-sm text-gray-400">Loading…</div>
            ) : candidates.length === 0 ? (
              <div className="text-sm text-gray-400">No match found.</div>
            ) : candidates.map((c) => (
              <div key={c.id} className="mb-2 last:mb-0">
                <div className="font-medium text-gray-900 dark:text-gray-100">{c.description || '(no description)'}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">{formatDate(c.date)} · {c.kind}</div>
                <div className="text-sm font-semibold">{formatCurrency(Number(c.amount))}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-6 flex flex-col sm:flex-row items-stretch sm:items-center sm:justify-end gap-2">
          <button
            onClick={onSkip}
            disabled={confirming}
            className="px-4 py-2 text-sm border rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
          >
            Skip — same transaction
          </button>
          <button
            onClick={onConfirm}
            disabled={confirming}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {confirming ? 'Adding…' : 'Add anyway — separate charge'}
          </button>
        </div>
      </div>
    </div>
  )
}

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

  const [dupDialog, setDupDialog] = useState<{ txn: PlaidTransaction; asType: 'expense' | 'income' } | null>(null)

  const categorizeMutation = useMutation({
    mutationFn: ({ txn, asType, confirm }: { txn: PlaidTransaction; asType: 'expense' | 'income' | 'ignore'; confirm?: boolean }) =>
      categorizePlaidTransaction(txn.id, { as_type: asType, confirm_duplicate: confirm }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plaid-transactions'] })
      setDupDialog(null)
    },
    onError: (err, variables) => {
      // Server flagged a likely duplicate — open the confirm dialog instead of
      // failing. (Only expense/income can collide; ignore never posts.)
      if (
        err instanceof ApiClientError &&
        err.status === 409 &&
        err.error?.code === 'PLAID_POSSIBLE_DUPLICATE' &&
        (variables.asType === 'expense' || variables.asType === 'income')
      ) {
        setDupDialog({ txn: variables.txn, asType: variables.asType })
      }
    },
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Bank Transactions</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            View and categorize transactions from connected bank accounts
          </p>
        </div>
        {connections.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => applyRulesMutation.mutate()}
              disabled={applyRulesMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
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
      <div className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex flex-wrap gap-3 items-center">
        <Filter className="w-4 h-4 text-gray-400 dark:text-gray-500" />
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
        <span className="text-sm text-gray-400 dark:text-gray-500 ml-auto">
          {meta.total} transaction{meta.total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Transactions */}
      {isLoading ? (
        <p className="text-gray-400 dark:text-gray-500 py-8 text-center text-sm">Loading transactions...</p>
      ) : transactions.length > 0 ? (
        <>
          <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 dark:bg-gray-950">
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Date</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Description</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Category</th>
                  <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Amount</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                  <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatDate(txn.date)}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{txn.merchant_name || txn.name}</div>
                      {txn.merchant_name && txn.name !== txn.merchant_name && (
                        <div className="text-xs text-gray-400 dark:text-gray-500">{txn.name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">{txn.category || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`flex items-center justify-end gap-1 font-medium ${txn.is_income ? 'text-green-600' : 'text-gray-900 dark:text-gray-100'}`}>
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
                        <span className="text-xs text-gray-400 dark:text-gray-500">Uncategorized</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!txn.is_categorized && (
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'expense' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-red-50 text-red-600 border-red-200"
                          >
                            Expense
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'income' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-green-50 text-green-600 border-green-200"
                          >
                            Income
                          </button>
                          <button
                            onClick={() => categorizeMutation.mutate({ txn, asType: 'ignore' })}
                            disabled={categorizeMutation.isPending}
                            className="px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
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
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Next
              </button>
            </div>
          )}
        </>
      ) : connections.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No bank accounts connected.</p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Go to Settings &gt; Banking to connect a bank account.
          </p>
        </div>
      ) : (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <Landmark className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No transactions found.</p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Click "Sync" to import transactions from your bank.
          </p>
        </div>
      )}

      {dupDialog && (
        <DuplicateDialog
          txn={dupDialog.txn}
          asType={dupDialog.asType}
          confirming={categorizeMutation.isPending}
          onSkip={() => setDupDialog(null)}
          onConfirm={() => categorizeMutation.mutate({ txn: dupDialog.txn, asType: dupDialog.asType, confirm: true })}
        />
      )}
    </div>
  )
}
