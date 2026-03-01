import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listAccounts,
  createAccount,
  listEntries,
  getSummary,
  listCategories,
} from '@/api/cashbook'
import { formatDate } from '@/lib/utils'
import { ACCOUNT_TYPES } from '@/lib/constants'
import {
  Plus,
  Search,
  BookOpen,
  Upload,
  Download,
  ChevronDown,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  Receipt,
} from 'lucide-react'
import type {
  CashbookEntryFilters,
  PaymentAccount,
  AccountType,
} from '@/types/models'
import ExcelImportDialog from '@/components/cashbook/ExcelImportDialog'

function formatCurrency(amount: number): string {
  return (
    '$' +
    Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  )
}

const currentYear = new Date().getFullYear()

export default function CashbookPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedAccountId, setSelectedAccountId] = useState<string>('')
  const [dateFrom, setDateFrom] = useState(`${currentYear}-01-01`)
  const [dateTo, setDateTo] = useState(`${currentYear}-12-31`)
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(1)
  const [showCategoryTotals, setShowCategoryTotals] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [showAddAccount, setShowAddAccount] = useState(false)

  // Add Account form state
  const [newAccountName, setNewAccountName] = useState('')
  const [newAccountType, setNewAccountType] = useState<AccountType>('bank')
  const [newAccountBalance, setNewAccountBalance] = useState('')
  const [newAccountDate, setNewAccountDate] = useState(
    new Date().toISOString().split('T')[0]
  )

  // Fetch accounts
  const { data: accountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
  })
  const accounts: PaymentAccount[] = accountsData?.data ?? []

  // Auto-select first account
  const activeAccountId =
    selectedAccountId || (accounts.length > 0 ? accounts[0].id : '')

  // Fetch entries
  const filters: CashbookEntryFilters = {
    account_id: activeAccountId || undefined,
    date_from: dateFrom,
    date_to: dateTo,
    search: searchTerm || undefined,
    page,
    page_size: 25,
  }

  const { data: entriesData, isLoading: entriesLoading } = useQuery({
    queryKey: ['cashbook-entries', filters],
    queryFn: () => listEntries(filters),
    enabled: !!activeAccountId,
  })
  const entries = entriesData?.data ?? []
  const meta = entriesData?.meta

  // Fetch summary
  const { data: summaryData } = useQuery({
    queryKey: ['cashbook-summary', activeAccountId, dateFrom, dateTo],
    queryFn: () => getSummary(activeAccountId, dateFrom, dateTo),
    enabled: !!activeAccountId,
  })
  const summary = summaryData?.data

  // Fetch categories
  const { data: _categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })

  // Create account mutation
  const createAccountMutation = useMutation({
    mutationFn: () =>
      createAccount({
        name: newAccountName,
        account_type: newAccountType,
        opening_balance: parseFloat(newAccountBalance) || 0,
        opening_balance_date: newAccountDate,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      setSelectedAccountId(data.data.id)
      setShowAddAccount(false)
      setNewAccountName('')
      setNewAccountType('bank')
      setNewAccountBalance('')
      setNewAccountDate(new Date().toISOString().split('T')[0])
    },
  })

  const handleSearch = () => {
    setSearchTerm(searchInput)
    setPage(1)
  }

  const totalPages = meta?.total_pages ?? 1
  const currentPage = meta?.page ?? 1

  const categoryTotals = summary?.category_totals ?? []
  const incomeTotals = categoryTotals.filter((ct) => ct.entry_type === 'income')
  const expenseTotals = categoryTotals.filter(
    (ct) => ct.entry_type === 'expense'
  )

  // Loading state while accounts load
  if (accountsLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-48" />
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    )
  }

  // No accounts state
  if (accounts.length === 0 && !showAddAccount) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Cashbook</h1>
        <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-12 text-center">
          <Wallet className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
            No Payment Accounts
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Create a payment account to start tracking your cashbook entries.
          </p>
          <button
            onClick={() => setShowAddAccount(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            Add Account
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Cashbook</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {meta?.total_count ?? 0} entries
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddAccount(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <Plus className="h-4 w-4" />
            Add Account
          </button>
          <button
            onClick={() => setShowImportDialog(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <Upload className="h-4 w-4" />
            Import Excel
          </button>
          {activeAccountId && (
            <a
              href={`/api/cashbook/export/csv?account_id=${activeAccountId}&date_from=${dateFrom}&date_to=${dateTo}`}
              download
              onClick={async (e) => {
                e.preventDefault()
                const token = localStorage.getItem('access_token')
                const res = await fetch(
                  `/api/cashbook/export/csv?account_id=${activeAccountId}&date_from=${dateFrom}&date_to=${dateTo}`,
                  { headers: token ? { Authorization: `Bearer ${token}` } : {} }
                )
                if (!res.ok) return
                const blob = await res.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `cashbook_${dateFrom}_${dateTo}.csv`
                a.click()
                URL.revokeObjectURL(url)
              }}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </a>
          )}
          <button
            onClick={() => navigate('/cashbook/new')}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            New Entry
          </button>
        </div>
      </div>

      {/* Add Account Dialog */}
      {showAddAccount && (
        <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Add Payment Account
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Account Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newAccountName}
                onChange={(e) => setNewAccountName(e.target.value)}
                placeholder="e.g., Business Checking"
                className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Account Type
              </label>
              <select
                value={newAccountType}
                onChange={(e) =>
                  setNewAccountType(e.target.value as AccountType)
                }
                className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {ACCOUNT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Opening Balance
              </label>
              <input
                type="number"
                step="0.01"
                value={newAccountBalance}
                onChange={(e) => setNewAccountBalance(e.target.value)}
                placeholder="0.00"
                className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Opening Date
              </label>
              <input
                type="date"
                value={newAccountDate}
                onChange={(e) => setNewAccountDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button
              onClick={() => setShowAddAccount(false)}
              className="px-4 py-2 text-sm border dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
            >
              Cancel
            </button>
            <button
              onClick={() => createAccountMutation.mutate()}
              disabled={!newAccountName || createAccountMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {createAccountMutation.isPending
                ? 'Creating...'
                : 'Create Account'}
            </button>
          </div>
          {createAccountMutation.isError && (
            <p className="text-sm text-red-600 mt-2">
              {(createAccountMutation.error as Error).message ||
                'Failed to create account'}
            </p>
          )}
        </div>
      )}

      {/* Account Tabs */}
      <div className="flex gap-1 border-b dark:border-gray-700">
        {accounts.map((account) => (
          <button
            key={account.id}
            onClick={() => {
              setSelectedAccountId(account.id)
              setPage(1)
            }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeAccountId === account.id
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
            }`}
          >
            {account.name}
            <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
              {ACCOUNT_TYPES.find((t) => t.value === account.account_type)
                ?.label ?? account.account_type}
            </span>
          </button>
        ))}
      </div>

      {/* Date Range & Search */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value)
              setPage(1)
            }}
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
            onChange={(e) => {
              setDateTo(e.target.value)
              setPage(1)
            }}
            className="px-3 py-2 text-sm border dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
        <div className="flex-1 flex gap-2">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search entries..."
              className="w-full pl-10 pr-4 py-2 text-sm border dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <button
            onClick={handleSearch}
            className="px-4 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
          >
            Search
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-1">
                <Wallet className="h-4 w-4" />
                Opening Balance
              </div>
              <p className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {summary.opening_balance < 0 ? '-' : ''}
                {formatCurrency(summary.opening_balance)}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-green-600 mb-1">
                <TrendingUp className="h-4 w-4" />
                Total Income
              </div>
              <p className="text-xl font-bold text-green-700">
                {formatCurrency(summary.total_income)}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-red-600 mb-1">
                <TrendingDown className="h-4 w-4" />
                Total Expenses
              </div>
              <p className="text-xl font-bold text-red-700">
                {formatCurrency(summary.total_expenses)}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-1">
                <DollarSign className="h-4 w-4" />
                Closing Balance
              </div>
              <p
                className={`text-xl font-bold ${summary.closing_balance >= 0 ? 'text-gray-900' : 'text-red-700'}`}
              >
                {summary.closing_balance < 0 ? '-' : ''}
                {formatCurrency(summary.closing_balance)}
              </p>
            </div>
          </div>

          {/* Tax Summary */}
          {(summary.total_tax_collected > 0 || summary.total_tax_paid > 0) && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
                <div className="flex items-center gap-2 text-sm text-green-600 mb-1">
                  <Receipt className="h-4 w-4" />
                  Tax Collected (HST)
                </div>
                <p className="text-lg font-bold text-green-700">
                  {formatCurrency(summary.total_tax_collected)}
                </p>
              </div>
              <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
                <div className="flex items-center gap-2 text-sm text-red-600 mb-1">
                  <Receipt className="h-4 w-4" />
                  Tax Paid (HST)
                </div>
                <p className="text-lg font-bold text-red-700">
                  {formatCurrency(summary.total_tax_paid)}
                </p>
              </div>
              <div className="bg-white dark:bg-gray-900 rounded-lg border p-4 col-span-2 md:col-span-1">
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-1">
                  <Receipt className="h-4 w-4" />
                  Net Tax (Owed/Refund)
                </div>
                <p
                  className={`text-lg font-bold ${
                    summary.total_tax_collected - summary.total_tax_paid >= 0
                      ? 'text-orange-600'
                      : 'text-blue-600'
                  }`}
                >
                  {summary.total_tax_collected - summary.total_tax_paid < 0
                    ? '-'
                    : ''}
                  {formatCurrency(
                    summary.total_tax_collected - summary.total_tax_paid
                  )}
                  <span className="text-xs font-normal text-gray-400 dark:text-gray-500 ml-2">
                    {summary.total_tax_collected - summary.total_tax_paid >= 0
                      ? '(owed)'
                      : '(refund)'}
                  </span>
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Entries Table */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Date
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Description
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Category
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Income
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Expense
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Tax
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                Balance
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {entriesLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={7} className="px-4 py-3">
                    <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                  </td>
                </tr>
              ))
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center">
                  <BookOpen className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 dark:text-gray-400 font-medium">No entries found</p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                    Create your first cashbook entry to get started.
                  </p>
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr
                  key={entry.id}
                  onClick={() => navigate(`/cashbook/entries/${entry.id}`)}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                >
                  <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                    {formatDate(entry.date)}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {entry.description}
                    </p>
                    {entry.notes && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                        {entry.notes}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {entry.category ? (
                      <span
                        className="inline-block px-2 py-0.5 text-xs rounded-full"
                        style={{
                          backgroundColor: entry.category.color
                            ? `${entry.category.color}20`
                            : '#f3f4f6',
                          color: entry.category.color || '#6b7280',
                        }}
                      >
                        {entry.category.name}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        Uncategorized
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right">
                    {entry.entry_type === 'income' ? (
                      <span className="font-medium text-green-700">
                        {formatCurrency(entry.total_amount)}
                      </span>
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right">
                    {entry.entry_type === 'expense' ? (
                      <span className="font-medium text-red-700">
                        {formatCurrency(entry.total_amount)}
                      </span>
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-400">
                    {entry.tax_amount != null && entry.tax_amount > 0
                      ? formatCurrency(entry.tax_amount)
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium">
                    {entry.bank_balance != null ? (
                      <span
                        className={
                          entry.bank_balance >= 0
                            ? 'text-gray-900 dark:text-gray-100'
                            : 'text-red-700'
                        }
                      >
                        {entry.bank_balance < 0 ? '-' : ''}
                        {formatCurrency(entry.bank_balance)}
                      </span>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-500">-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Page {currentPage} of {totalPages} ({meta?.total_count} total)
          </p>
          <div className="flex gap-1">
            <button
              disabled={currentPage <= 1}
              onClick={() => setPage(currentPage - 1)}
              className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
            >
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setPage(currentPage + 1)}
              className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Category Totals */}
      {summary && categoryTotals.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700">
          <button
            onClick={() => setShowCategoryTotals(!showCategoryTotals)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span>Category Totals</span>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${showCategoryTotals ? 'rotate-180' : ''}`}
            />
          </button>
          {showCategoryTotals && (
            <div className="px-4 pb-4">
              {incomeTotals.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-2">
                    Income by Category
                  </h4>
                  <div className="space-y-1">
                    {incomeTotals.map((ct) => (
                      <div
                        key={`income-${ct.category_id ?? 'uncategorized'}`}
                        className="flex items-center justify-between text-sm py-1"
                      >
                        <span className="text-gray-700 dark:text-gray-300">
                          {ct.category_name}{' '}
                          <span className="text-gray-400 dark:text-gray-500">
                            ({ct.count} entries)
                          </span>
                        </span>
                        <div className="flex gap-4">
                          <span className="text-green-700 font-medium">
                            {formatCurrency(ct.total_amount)}
                          </span>
                          {ct.total_tax > 0 && (
                            <span className="text-gray-500 dark:text-gray-400 text-xs">
                              Tax: {formatCurrency(ct.total_tax)}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {expenseTotals.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-2">
                    Expenses by Category
                  </h4>
                  <div className="space-y-1">
                    {expenseTotals.map((ct) => (
                      <div
                        key={`expense-${ct.category_id ?? 'uncategorized'}`}
                        className="flex items-center justify-between text-sm py-1"
                      >
                        <span className="text-gray-700 dark:text-gray-300">
                          {ct.category_name}{' '}
                          <span className="text-gray-400 dark:text-gray-500">
                            ({ct.count} entries)
                          </span>
                        </span>
                        <div className="flex gap-4">
                          <span className="text-red-700 font-medium">
                            {formatCurrency(ct.total_amount)}
                          </span>
                          {ct.total_tax > 0 && (
                            <span className="text-gray-500 dark:text-gray-400 text-xs">
                              Tax: {formatCurrency(ct.total_tax)}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Excel Import Dialog */}
      <ExcelImportDialog
        isOpen={showImportDialog}
        onClose={() => setShowImportDialog(false)}
        accounts={accounts}
        onImported={() => {
          queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
          queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
        }}
      />
    </div>
  )
}
