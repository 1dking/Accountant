import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  findMatches,
  listMatches,
  confirmMatch,
  rejectMatch,
  createManualMatch,
  getUnmatchedReceipts,
  getUnmatchedTransactions,
  getReconciliationSummary,
} from '@/api/reconciliation'
import { toast } from 'sonner'
import {
  Scale,
  Search,
  Check,
  X,
  Link,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  ArrowRightLeft,
  Loader2,
} from 'lucide-react'
import type {
  MatchResponse,
  ReconciliationSummary,
  Expense,
  CashbookEntry,
} from '@/types/models'

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

type TabKey = 'matches' | 'unmatched-receipts' | 'unmatched-transactions'

export default function ReconciliationPage() {
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState<TabKey>('matches')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [matchesPage, setMatchesPage] = useState(1)
  const [receiptsPage, setReceiptsPage] = useState(1)
  const [transactionsPage, setTransactionsPage] = useState(1)

  // Manual match modal state
  const [matchReceiptModal, setMatchReceiptModal] = useState<{
    open: boolean
    receipt: Expense | null
  }>({ open: false, receipt: null })
  const [matchTransactionModal, setMatchTransactionModal] = useState<{
    open: boolean
    transaction: CashbookEntry | null
  }>({ open: false, transaction: null })

  // Summary
  const { data: summaryData } = useQuery({
    queryKey: ['reconciliation-summary'],
    queryFn: () => getReconciliationSummary(),
  })
  const summary: ReconciliationSummary | undefined = summaryData?.data

  // Matches
  const { data: matchesData, isLoading: matchesLoading } = useQuery({
    queryKey: ['reconciliation-matches', matchesPage],
    queryFn: () => listMatches(undefined, matchesPage, 50),
  })
  const matches: MatchResponse[] = matchesData?.data ?? []
  const matchesMeta = matchesData?.meta

  // Unmatched receipts
  const { data: unmatchedReceiptsData, isLoading: receiptsLoading } = useQuery({
    queryKey: ['reconciliation-unmatched-receipts', receiptsPage],
    queryFn: () => getUnmatchedReceipts(receiptsPage, 50),
  })
  const unmatchedReceipts: Expense[] = unmatchedReceiptsData?.data ?? []
  const receiptsMeta = unmatchedReceiptsData?.meta

  // Unmatched transactions
  const { data: unmatchedTransactionsData, isLoading: transactionsLoading } =
    useQuery({
      queryKey: ['reconciliation-unmatched-transactions', transactionsPage],
      queryFn: () => getUnmatchedTransactions(transactionsPage, 50),
    })
  const unmatchedTransactions: CashbookEntry[] =
    unmatchedTransactionsData?.data ?? []
  const transactionsMeta = unmatchedTransactionsData?.meta

  // Transactions for receipt modal selection
  const { data: allTransactionsData } = useQuery({
    queryKey: ['reconciliation-unmatched-transactions-for-modal'],
    queryFn: () => getUnmatchedTransactions(1, 100),
    enabled: matchReceiptModal.open,
  })
  const allUnmatchedTransactions: CashbookEntry[] =
    allTransactionsData?.data ?? []

  // Receipts for transaction modal selection
  const { data: allReceiptsData } = useQuery({
    queryKey: ['reconciliation-unmatched-receipts-for-modal'],
    queryFn: () => getUnmatchedReceipts(1, 100),
    enabled: matchTransactionModal.open,
  })
  const allUnmatchedReceipts: Expense[] = allReceiptsData?.data ?? []

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['reconciliation-summary'] })
    queryClient.invalidateQueries({ queryKey: ['reconciliation-matches'] })
    queryClient.invalidateQueries({
      queryKey: ['reconciliation-unmatched-receipts'],
    })
    queryClient.invalidateQueries({
      queryKey: ['reconciliation-unmatched-transactions'],
    })
  }

  // Find matches mutation
  const findMatchesMutation = useMutation({
    mutationFn: () => findMatches(dateFrom || undefined, dateTo || undefined),
    onSuccess: (data) => {
      const count = data?.data?.length ?? 0
      toast.success(`Found ${count} potential match${count !== 1 ? 'es' : ''}`)
      invalidateAll()
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to find matches')
    },
  })

  // Confirm match mutation
  const confirmMutation = useMutation({
    mutationFn: (matchId: string) => confirmMatch(matchId),
    onSuccess: () => {
      toast.success('Match confirmed')
      invalidateAll()
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to confirm match')
    },
  })

  // Reject match mutation
  const rejectMutation = useMutation({
    mutationFn: (matchId: string) => rejectMatch(matchId),
    onSuccess: () => {
      toast.success('Match rejected')
      invalidateAll()
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to reject match')
    },
  })

  // Manual match mutation
  const manualMatchMutation = useMutation({
    mutationFn: ({
      receiptId,
      transactionId,
    }: {
      receiptId: string
      transactionId: string
    }) => createManualMatch(receiptId, transactionId),
    onSuccess: () => {
      toast.success('Manual match created')
      setMatchReceiptModal({ open: false, receipt: null })
      setMatchTransactionModal({ open: false, transaction: null })
      invalidateAll()
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to create match')
    },
  })

  const confidenceBadge = (confidence: number) => {
    const pct = Math.round(confidence * 100)
    let colorClasses: string
    if (pct >= 80) {
      colorClasses =
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    } else if (pct >= 50) {
      colorClasses =
        'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
    } else {
      colorClasses =
        'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
    }
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${colorClasses}`}
      >
        {pct}%
      </span>
    )
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'confirmed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
            <CheckCircle className="h-3 w-3" />
            Confirmed
          </span>
        )
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
            <XCircle className="h-3 w-3" />
            Rejected
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
            <Clock className="h-3 w-3" />
            Pending
          </span>
        )
    }
  }

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'matches', label: 'Matches', count: matchesMeta?.total_count },
    {
      key: 'unmatched-receipts',
      label: 'Unmatched Receipts',
      count: receiptsMeta?.total_count,
    },
    {
      key: 'unmatched-transactions',
      label: 'Unmatched Transactions',
      count: transactionsMeta?.total_count,
    },
  ]

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <Scale className="h-7 w-7 text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Reconciliation
          </h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 ml-10">
          Match receipts to bank transactions
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 text-sm text-amber-600 mb-1">
            <Clock className="h-4 w-4" />
            Pending Matches
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {summary?.pending_matches ?? 0}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 text-sm text-green-600 mb-1">
            <CheckCircle className="h-4 w-4" />
            Confirmed Matches
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {summary?.confirmed_matches ?? 0}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 text-sm text-red-600 mb-1">
            <FileText className="h-4 w-4" />
            Unmatched Receipts
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {summary?.unmatched_receipts ?? 0}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-1">
            <ArrowRightLeft className="h-4 w-4" />
            Unmatched Transactions
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {summary?.unmatched_transactions ?? 0}
          </p>
        </div>
      </div>

      {/* Find Matches */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
        <button
          onClick={() => findMatchesMutation.mutate()}
          disabled={findMatchesMutation.isPending}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {findMatchesMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          {findMatchesMutation.isPending ? 'Finding...' : 'Find Matches'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b dark:border-gray-700">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
            }`}
          >
            {tab.label}
            {tab.count != null && (
              <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                ({tab.count})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Matches Tab */}
      {activeTab === 'matches' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Receipt
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Receipt Amt
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Transaction
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Trans Amt
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Confidence
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Status
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {matchesLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-4 py-3">
                      <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                    </td>
                  </tr>
                ))
              ) : matches.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <Scale className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400 font-medium">
                      No matches found
                    </p>
                    <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                      Use "Find Matches" to automatically match receipts with
                      transactions.
                    </p>
                  </td>
                </tr>
              ) : (
                matches.map((match) => (
                  <tr
                    key={match.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {match.receipt_vendor || 'Unknown vendor'}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(match.receipt_date)}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(match.receipt_amount)}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {match.transaction_description}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(match.transaction_date)}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(match.transaction_amount)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {confidenceBadge(match.match_confidence)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {statusBadge(match.status)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {match.status === 'pending' && (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => confirmMutation.mutate(match.id)}
                            disabled={confirmMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-green-700 bg-green-50 dark:bg-green-900/20 dark:text-green-400 rounded-md hover:bg-green-100 dark:hover:bg-green-900/40 disabled:opacity-50"
                            title="Confirm match"
                          >
                            <Check className="h-3.5 w-3.5" />
                            Confirm
                          </button>
                          <button
                            onClick={() => rejectMutation.mutate(match.id)}
                            disabled={rejectMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-red-700 bg-red-50 dark:bg-red-900/20 dark:text-red-400 rounded-md hover:bg-red-100 dark:hover:bg-red-900/40 disabled:opacity-50"
                            title="Reject match"
                          >
                            <X className="h-3.5 w-3.5" />
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Matches Pagination */}
          {(matchesMeta?.total_pages ?? 1) > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {matchesMeta?.page ?? 1} of {matchesMeta?.total_pages ?? 1}{' '}
                ({matchesMeta?.total_count} total)
              </p>
              <div className="flex gap-1">
                <button
                  disabled={(matchesMeta?.page ?? 1) <= 1}
                  onClick={() => setMatchesPage((p) => p - 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Previous
                </button>
                <button
                  disabled={
                    (matchesMeta?.page ?? 1) >= (matchesMeta?.total_pages ?? 1)
                  }
                  onClick={() => setMatchesPage((p) => p + 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Unmatched Receipts Tab */}
      {activeTab === 'unmatched-receipts' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Vendor
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Amount
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Date
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {receiptsLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={4} className="px-4 py-3">
                      <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                    </td>
                  </tr>
                ))
              ) : unmatchedReceipts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center">
                    <CheckCircle className="h-12 w-12 text-green-300 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400 font-medium">
                      All receipts are matched
                    </p>
                  </td>
                </tr>
              ) : (
                unmatchedReceipts.map((receipt) => (
                  <tr
                    key={receipt.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {receipt.vendor_name || 'Unknown vendor'}
                      </p>
                      {receipt.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[250px]">
                          {receipt.description}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(receipt.amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {formatDate(receipt.date)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() =>
                          setMatchReceiptModal({ open: true, receipt })
                        }
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-400 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/40"
                      >
                        <Link className="h-3.5 w-3.5" />
                        Match
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Receipts Pagination */}
          {(receiptsMeta?.total_pages ?? 1) > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {receiptsMeta?.page ?? 1} of{' '}
                {receiptsMeta?.total_pages ?? 1} ({receiptsMeta?.total_count}{' '}
                total)
              </p>
              <div className="flex gap-1">
                <button
                  disabled={(receiptsMeta?.page ?? 1) <= 1}
                  onClick={() => setReceiptsPage((p) => p - 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Previous
                </button>
                <button
                  disabled={
                    (receiptsMeta?.page ?? 1) >=
                    (receiptsMeta?.total_pages ?? 1)
                  }
                  onClick={() => setReceiptsPage((p) => p + 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Unmatched Transactions Tab */}
      {activeTab === 'unmatched-transactions' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Description
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Amount
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Date
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {transactionsLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={4} className="px-4 py-3">
                      <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                    </td>
                  </tr>
                ))
              ) : unmatchedTransactions.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center">
                    <CheckCircle className="h-12 w-12 text-green-300 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400 font-medium">
                      All transactions are matched
                    </p>
                  </td>
                </tr>
              ) : (
                unmatchedTransactions.map((txn) => (
                  <tr
                    key={txn.id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {txn.description}
                      </p>
                      {txn.notes && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[250px]">
                          {txn.notes}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(txn.total_amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {formatDate(txn.date)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() =>
                          setMatchTransactionModal({
                            open: true,
                            transaction: txn,
                          })
                        }
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-400 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/40"
                      >
                        <Link className="h-3.5 w-3.5" />
                        Match
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Transactions Pagination */}
          {(transactionsMeta?.total_pages ?? 1) > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Page {transactionsMeta?.page ?? 1} of{' '}
                {transactionsMeta?.total_pages ?? 1} (
                {transactionsMeta?.total_count} total)
              </p>
              <div className="flex gap-1">
                <button
                  disabled={(transactionsMeta?.page ?? 1) <= 1}
                  onClick={() => setTransactionsPage((p) => p - 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Previous
                </button>
                <button
                  disabled={
                    (transactionsMeta?.page ?? 1) >=
                    (transactionsMeta?.total_pages ?? 1)
                  }
                  onClick={() => setTransactionsPage((p) => p + 1)}
                  className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Manual Match Modal: Select a Transaction for a Receipt */}
      {matchReceiptModal.open && matchReceiptModal.receipt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() =>
              setMatchReceiptModal({ open: false, receipt: null })
            }
          />
          <div className="relative bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-lg max-h-[80vh] flex flex-col">
            <div className="px-5 py-4 border-b dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Select a Transaction
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Match receipt from{' '}
                <span className="font-medium text-gray-700 dark:text-gray-300">
                  {matchReceiptModal.receipt.vendor_name || 'Unknown vendor'}
                </span>{' '}
                ({formatCurrency(matchReceiptModal.receipt.amount)}) to a
                transaction
              </p>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {allUnmatchedTransactions.length === 0 ? (
                <div className="py-8 text-center">
                  <AlertTriangle className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No unmatched transactions available
                  </p>
                </div>
              ) : (
                allUnmatchedTransactions.map((txn) => (
                  <button
                    key={txn.id}
                    onClick={() =>
                      manualMatchMutation.mutate({
                        receiptId: matchReceiptModal.receipt!.id,
                        transactionId: txn.id,
                      })
                    }
                    disabled={manualMatchMutation.isPending}
                    className="w-full flex items-center justify-between px-4 py-3 text-left rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {txn.description}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(txn.date)}
                      </p>
                    </div>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(txn.total_amount)}
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="px-5 py-3 border-t dark:border-gray-700 flex justify-end">
              <button
                onClick={() =>
                  setMatchReceiptModal({ open: false, receipt: null })
                }
                className="px-4 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Match Modal: Select a Receipt for a Transaction */}
      {matchTransactionModal.open && matchTransactionModal.transaction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() =>
              setMatchTransactionModal({ open: false, transaction: null })
            }
          />
          <div className="relative bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-lg max-h-[80vh] flex flex-col">
            <div className="px-5 py-4 border-b dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Select a Receipt
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Match transaction{' '}
                <span className="font-medium text-gray-700 dark:text-gray-300">
                  {matchTransactionModal.transaction.description}
                </span>{' '}
                (
                {formatCurrency(
                  matchTransactionModal.transaction.total_amount
                )}
                ) to a receipt
              </p>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {allUnmatchedReceipts.length === 0 ? (
                <div className="py-8 text-center">
                  <AlertTriangle className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No unmatched receipts available
                  </p>
                </div>
              ) : (
                allUnmatchedReceipts.map((receipt) => (
                  <button
                    key={receipt.id}
                    onClick={() =>
                      manualMatchMutation.mutate({
                        receiptId: receipt.id,
                        transactionId:
                          matchTransactionModal.transaction!.id,
                      })
                    }
                    disabled={manualMatchMutation.isPending}
                    className="w-full flex items-center justify-between px-4 py-3 text-left rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {receipt.vendor_name || 'Unknown vendor'}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(receipt.date)}
                      </p>
                    </div>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(receipt.amount)}
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="px-5 py-3 border-t dark:border-gray-700 flex justify-end">
              <button
                onClick={() =>
                  setMatchTransactionModal({ open: false, transaction: null })
                }
                className="px-4 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
