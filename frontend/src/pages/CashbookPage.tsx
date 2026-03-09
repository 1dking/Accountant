import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  listAccounts,
  createAccount,
  deleteAccount,
  listEntries,
  getSummary,
  listCategories,
  bulkDeleteEntries,
  bulkCategorizeEntries,
  bulkMoveEntries,
  bulkUpdateStatus,
  restoreEntry,
  fixOrphanEntries,
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
  Trash2,
  Pencil,
  Scissors,
  RotateCcw,
  CheckSquare,
  Circle,
  CheckCircle2,
  XCircle,
  Shield,
  X,
} from 'lucide-react'
import type {
  CashbookEntryFilters,
  PaymentAccount,
  AccountType,
  CashbookEntry,
  TransactionCategory,
} from '@/types/models'
import ExcelImportDialog from '@/components/cashbook/ExcelImportDialog'
import EditEntryModal from '@/components/cashbook/EditEntryModal'
import SplitEntryModal from '@/components/cashbook/SplitEntryModal'

function formatCurrency(amount: number): string {
  return (
    '$' +
    Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  )
}

const STATUS_ICONS: Record<string, typeof Circle> = {
  pending: Circle,
  cleared: CheckCircle2,
  reconciled: Shield,
  voided: XCircle,
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'text-yellow-500',
  cleared: 'text-blue-500',
  reconciled: 'text-green-500',
  voided: 'text-red-400',
}

const currentYear = new Date().getFullYear()

export default function CashbookPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedAccountId, setSelectedAccountId] = useState<string>('all')
  const [entryTypeFilter, setEntryTypeFilter] = useState<'all' | 'income' | 'expense'>('all')
  const [dateFrom, setDateFrom] = useState(`${currentYear}-01-01`)
  const [dateTo, setDateTo] = useState(`${currentYear}-12-31`)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(1)
  const [showCategoryTotals, setShowCategoryTotals] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [showAddAccount, setShowAddAccount] = useState(false)

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Modals
  const [editEntry, setEditEntry] = useState<CashbookEntry | null>(null)
  const [splitEntryTarget, setSplitEntryTarget] = useState<CashbookEntry | null>(null)

  // Bulk action dropdowns
  const [showBulkCategorize, setShowBulkCategorize] = useState(false)
  const [showBulkMove, setShowBulkMove] = useState(false)
  const [bulkCategoryId, setBulkCategoryId] = useState('')
  const [bulkMoveAccountId, setBulkMoveAccountId] = useState('')

  // Add Account form
  const [newAccountName, setNewAccountName] = useState('')
  const [newAccountType, setNewAccountType] = useState<AccountType>('bank')
  const [newAccountCurrency, setNewAccountCurrency] = useState('CAD')
  const [newAccountBalance, setNewAccountBalance] = useState('')
  const [newAccountDate, setNewAccountDate] = useState(new Date().toISOString().split('T')[0])

  // Fetch accounts
  const { data: accountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
  })
  const accounts: PaymentAccount[] = accountsData?.data ?? []
  const activeAccountId = selectedAccountId

  // Fetch entries
  const filters: CashbookEntryFilters = {
    account_id: activeAccountId !== 'all' ? activeAccountId : undefined,
    entry_type: entryTypeFilter !== 'all' ? entryTypeFilter : undefined,
    status: statusFilter !== 'all' ? statusFilter as any : undefined,
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
  const entries: CashbookEntry[] = entriesData?.data ?? []
  const meta = entriesData?.meta

  // Fetch summary
  const { data: summaryData } = useQuery({
    queryKey: ['cashbook-summary', activeAccountId, dateFrom, dateTo],
    queryFn: () => getSummary(activeAccountId, dateFrom, dateTo),
    enabled: !!activeAccountId && activeAccountId !== 'all',
  })
  const summary = summaryData?.data

  const allAccountsSummary = activeAccountId === 'all' && entries.length > 0 ? {
    total_income: entries.filter(e => e.entry_type === 'income').reduce((s, e) => s + e.total_amount, 0),
    total_expenses: entries.filter(e => e.entry_type === 'expense').reduce((s, e) => s + e.total_amount, 0),
    opening_balance: 0,
    closing_balance: 0,
  } : null

  const accountMap = new Map(accounts.map(a => [a.id, a]))

  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const categories: TransactionCategory[] = categoriesData?.data ?? []

  // Mutations
  const createAccountMutation = useMutation({
    mutationFn: () =>
      createAccount({
        name: newAccountName,
        account_type: newAccountType,
        currency: newAccountCurrency,
        opening_balance: parseFloat(newAccountBalance) || 0,
        opening_balance_date: newAccountDate,
      }),
    onSuccess: (data) => {
      // Optimistically add new account to cache so UI updates instantly
      queryClient.setQueryData(['cashbook-accounts'], (old: any) => ({
        ...(old ?? {}),
        data: [...(old?.data ?? []), data.data],
      }))
      // Then refetch everything in background for fresh data
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      setSelectedAccountId(data.data.id)
      setShowAddAccount(false)
      setNewAccountName('')
      setNewAccountType('bank')
      setNewAccountCurrency('CAD')
      setNewAccountBalance('')
      setNewAccountDate(new Date().toISOString().split('T')[0])
      toast.success(`Account "${data.data.name}" created`)
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to create account')
    },
  })

  const deleteAccountMutation = useMutation({
    mutationFn: (accountId: string) => deleteAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      setSelectedAccountId('all')
    },
  })

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => bulkDeleteEntries(ids),
    onSuccess: (data) => {
      toast.success(`Deleted ${data.data.deleted} entries`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
    },
  })

  const bulkCategorizeMutation = useMutation({
    mutationFn: ({ ids, catId }: { ids: string[]; catId: string }) => bulkCategorizeEntries(ids, catId),
    onSuccess: (data) => {
      toast.success(`Categorized ${data.data.updated} entries`)
      setSelectedIds(new Set())
      setShowBulkCategorize(false)
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
    },
  })

  const bulkMoveMutation = useMutation({
    mutationFn: ({ ids, acctId }: { ids: string[]; acctId: string }) => bulkMoveEntries(ids, acctId),
    onSuccess: (data) => {
      toast.success(`Moved ${data.data.moved} entries`)
      setSelectedIds(new Set())
      setShowBulkMove(false)
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
    },
  })

  const bulkStatusMutation = useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: string }) => bulkUpdateStatus(ids, status),
    onSuccess: (data) => {
      toast.success(`Updated ${data.data.updated} entries`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
    },
  })

  const restoreMutation = useMutation({
    mutationFn: restoreEntry,
    onSuccess: () => {
      toast.success('Entry restored')
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
    },
  })

  // Fix orphan entries on page load (one-shot)
  const orphanFixedRef = useRef(false)
  const fixOrphanMutation = useMutation({
    mutationFn: fixOrphanEntries,
    onSuccess: (data) => {
      if (data.data.reassigned > 0) {
        queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
        queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
        toast.success(`Assigned ${data.data.reassigned} orphan entries to your first account`)
      }
    },
  })
  useEffect(() => {
    if (accounts.length > 0 && !orphanFixedRef.current) {
      orphanFixedRef.current = true
      fixOrphanMutation.mutate()
    }
  }, [accounts.length])

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === entries.length) setSelectedIds(new Set())
    else setSelectedIds(new Set(entries.map(e => e.id)))
  }, [entries, selectedIds.size])

  const handleDeleteAccount = (account: PaymentAccount) => {
    if (confirm(`Delete "${account.name}"?`)) deleteAccountMutation.mutate(account.id)
  }

  const handleSearch = () => { setSearchTerm(searchInput); setPage(1) }

  const totalPages = meta?.total_pages ?? 1
  const currentPage = meta?.page ?? 1
  const categoryTotals = summary?.category_totals ?? []
  const incomeTotals = categoryTotals.filter((ct: any) => ct.entry_type === 'income')
  const expenseTotals = categoryTotals.filter((ct: any) => ct.entry_type === 'expense')

  const AddAccountModal = () => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowAddAccount(false)}>
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl border dark:border-gray-700 w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Add Payment Account</h3>
          <button onClick={() => setShowAddAccount(false)} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account Name *</label>
            <input type="text" value={newAccountName} onChange={e => setNewAccountName(e.target.value)} placeholder="Business Checking" className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
              <select value={newAccountType} onChange={e => setNewAccountType(e.target.value as AccountType)} className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 dark:text-gray-100">
                {ACCOUNT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Currency</label>
              <select value={newAccountCurrency} onChange={e => setNewAccountCurrency(e.target.value)} className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 dark:text-gray-100">
                <option value="CAD">CAD</option>
                <option value="USD">USD</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Opening Balance</label>
              <input type="number" step="0.01" value={newAccountBalance} onChange={e => setNewAccountBalance(e.target.value)} placeholder="0.00" className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">As of Date *</label>
              <input type="date" value={newAccountDate} onChange={e => setNewAccountDate(e.target.value)} className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          </div>
        </div>
        {createAccountMutation.isError && (
          <div className="mx-6 mb-0 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
            {(createAccountMutation.error as any)?.message || 'Failed to create account'}
          </div>
        )}
        <div className="flex justify-end gap-2 px-6 py-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl">
          <button onClick={() => setShowAddAccount(false)} className="px-4 py-2 text-sm border dark:border-gray-600 rounded-lg dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
          <button onClick={() => createAccountMutation.mutate()} disabled={!newAccountName || createAccountMutation.isPending} className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {createAccountMutation.isPending ? 'Creating...' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  )

  if (accountsLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-48" />
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    )
  }

  /* No empty-state gate — page always renders fully */

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Cashbook</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{meta?.total_count ?? 0} entries</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setShowAddAccount(true)} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
            <Plus className="h-4 w-4" /> Add Account
          </button>
          <button onClick={() => setShowImportDialog(true)} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
            <Upload className="h-4 w-4" /> Import
          </button>
          {activeAccountId !== 'all' && (
            <a
              href="#"
              onClick={async (e) => {
                e.preventDefault()
                const token = localStorage.getItem('access_token')
                const res = await fetch(`/api/cashbook/export/csv?account_id=${activeAccountId}&date_from=${dateFrom}&date_to=${dateTo}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
                if (!res.ok) return
                const blob = await res.blob()
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `cashbook_${dateFrom}_${dateTo}.csv`
                a.click()
                URL.revokeObjectURL(url)
              }}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
            >
              <Download className="h-4 w-4" /> CSV
            </a>
          )}
          <button onClick={() => navigate('/cashbook/new')} className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700">
            <Plus className="h-4 w-4" /> New Entry
          </button>
        </div>
      </div>

      {/* Add Account Modal */}
      {showAddAccount && <AddAccountModal />}

      {/* No-accounts banner */}
      {accounts.length === 0 && (
        <div className="flex items-center gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
          <Wallet className="h-5 w-5 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800 dark:text-amber-300">Create a payment account to start tracking income and expenses.</p>
          <button onClick={() => setShowAddAccount(true)} className="ml-auto shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700">
            <Plus className="h-3.5 w-3.5" /> Add Account
          </button>
        </div>
      )}

      {/* Account Tabs */}
      <div className="flex items-center gap-1 border-b dark:border-gray-700 overflow-x-auto">
        <button onClick={() => { setSelectedAccountId('all'); setPage(1); setSelectedIds(new Set()) }} className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${activeAccountId === 'all' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700'}`}>
          All Accounts
        </button>
        {accounts.map(account => (
          <button key={account.id} onClick={() => { setSelectedAccountId(account.id); setPage(1); setSelectedIds(new Set()) }} className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${activeAccountId === account.id ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700'}`}>
            {account.name}
            <span className="ml-2 text-xs text-gray-400">{ACCOUNT_TYPES.find(t => t.value === account.account_type)?.label ?? ''} ({account.currency || 'CAD'})</span>
          </button>
        ))}
        {activeAccountId !== 'all' && (
          <button onClick={() => handleDeleteAccount(accounts.find(a => a.id === activeAccountId)!)} disabled={deleteAccountMutation.isPending} className="ml-auto px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg flex items-center gap-1 disabled:opacity-50">
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex gap-1">
          {(['all', 'income', 'expense'] as const).map(type => (
            <button key={type} onClick={() => { setEntryTypeFilter(type); setPage(1) }} className={`px-3 py-1.5 text-sm font-medium rounded-lg ${
              entryTypeFilter === type
                ? type === 'income' ? 'bg-green-100 dark:bg-green-900/30 text-green-700' : type === 'expense' ? 'bg-red-100 dark:bg-red-900/30 text-red-700' : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700'
                : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
            }`}>
              {type === 'all' ? 'All' : type === 'income' ? 'Income' : 'Expenses'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['all', 'pending', 'cleared', 'reconciled'] as const).map(st => {
            const Icon = st !== 'all' ? STATUS_ICONS[st] : null
            const color = st !== 'all' ? STATUS_COLORS[st] : ''
            return (
              <button key={st} onClick={() => { setStatusFilter(st); setPage(1) }} className={`px-3 py-1.5 text-sm font-medium rounded-lg flex items-center gap-1.5 ${
                statusFilter === st
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
                  : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}>
                {Icon && <Icon className={`h-3.5 w-3.5 ${color}`} />}
                {st === 'all' ? 'All Status' : st.charAt(0).toUpperCase() + st.slice(1)}
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-2">
          <input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1) }} className="px-3 py-1.5 text-sm border dark:border-gray-600 rounded-md dark:bg-gray-800 dark:text-gray-100" />
          <span className="text-gray-400 text-xs">to</span>
          <input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1) }} className="px-3 py-1.5 text-sm border dark:border-gray-600 rounded-md dark:bg-gray-800 dark:text-gray-100" />
        </div>
        <div className="flex-1 flex gap-2 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input type="text" value={searchInput} onChange={e => setSearchInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} placeholder="Search..." className="w-full pl-10 pr-4 py-1.5 text-sm border dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-gray-100" />
          </div>
          <button onClick={handleSearch} className="px-3 py-1.5 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300">Go</button>
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg flex-wrap">
          <CheckSquare className="w-4 h-4 text-blue-600" />
          <span className="text-sm font-medium text-blue-700 dark:text-blue-300">{selectedIds.size} selected</span>
          <div className="flex gap-1 ml-3 flex-wrap">
            <button onClick={() => bulkDeleteMutation.mutate(Array.from(selectedIds))} className="px-2.5 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700">Delete</button>
            <div className="relative">
              <button onClick={() => { setShowBulkCategorize(!showBulkCategorize); setShowBulkMove(false) }} className="px-2.5 py-1 text-xs bg-white dark:bg-gray-800 border rounded hover:bg-gray-50 dark:text-gray-300">Categorize</button>
              {showBulkCategorize && (
                <div className="absolute top-8 left-0 z-20 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg p-3 w-60">
                  <select value={bulkCategoryId} onChange={e => setBulkCategoryId(e.target.value)} className="w-full px-2 py-1.5 text-sm border rounded dark:bg-gray-900 dark:border-gray-700 dark:text-gray-100 mb-2">
                    <option value="">Select...</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <button onClick={() => bulkCategoryId && bulkCategorizeMutation.mutate({ ids: Array.from(selectedIds), catId: bulkCategoryId })} disabled={!bulkCategoryId} className="w-full px-2 py-1 text-xs bg-blue-600 text-white rounded disabled:opacity-50">Apply</button>
                </div>
              )}
            </div>
            <div className="relative">
              <button onClick={() => { setShowBulkMove(!showBulkMove); setShowBulkCategorize(false) }} className="px-2.5 py-1 text-xs bg-white dark:bg-gray-800 border rounded hover:bg-gray-50 dark:text-gray-300">Move</button>
              {showBulkMove && (
                <div className="absolute top-8 left-0 z-20 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg p-3 w-60">
                  <select value={bulkMoveAccountId} onChange={e => setBulkMoveAccountId(e.target.value)} className="w-full px-2 py-1.5 text-sm border rounded dark:bg-gray-900 dark:border-gray-700 dark:text-gray-100 mb-2">
                    <option value="">Select...</option>
                    {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                  <button onClick={() => bulkMoveAccountId && bulkMoveMutation.mutate({ ids: Array.from(selectedIds), acctId: bulkMoveAccountId })} disabled={!bulkMoveAccountId} className="w-full px-2 py-1 text-xs bg-blue-600 text-white rounded disabled:opacity-50">Move</button>
                </div>
              )}
            </div>
            {(['cleared', 'reconciled', 'pending'] as const).map(st => (
              <button key={st} onClick={() => bulkStatusMutation.mutate({ ids: Array.from(selectedIds), status: st })} className="px-2.5 py-1 text-xs bg-white dark:bg-gray-800 border rounded hover:bg-gray-50 dark:text-gray-300 capitalize">
                {st}
              </button>
            ))}
          </div>
          <button onClick={() => setSelectedIds(new Set())} className="ml-auto text-xs text-gray-500 hover:text-gray-700">Clear</button>
        </div>
      )}

      {/* Stats */}
      {(summary || allAccountsSummary) && (() => {
        const s = summary ?? allAccountsSummary!
        return (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {activeAccountId !== 'all' && (
              <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><Wallet className="h-4 w-4" /> Opening</div>
                <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{s.opening_balance < 0 ? '-' : ''}{formatCurrency(s.opening_balance)}</p>
              </div>
            )}
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-green-600 mb-1"><TrendingUp className="h-4 w-4" /> Income</div>
              <p className="text-xl font-bold text-green-700">{formatCurrency(s.total_income)}</p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-red-600 mb-1"><TrendingDown className="h-4 w-4" /> Expenses</div>
              <p className="text-xl font-bold text-red-700">{formatCurrency(s.total_expenses)}</p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1"><DollarSign className="h-4 w-4" /> {activeAccountId !== 'all' ? 'Closing' : 'Net'}</div>
              <p className={`text-xl font-bold ${(activeAccountId !== 'all' ? s.closing_balance : s.total_income - s.total_expenses) >= 0 ? 'text-gray-900 dark:text-gray-100' : 'text-red-700'}`}>
                {formatCurrency(activeAccountId !== 'all' ? s.closing_balance : s.total_income - s.total_expenses)}
              </p>
            </div>
          </div>
        )
      })()}

      {/* Tax Row */}
      {summary && (summary.total_tax_collected > 0 || summary.total_tax_paid > 0) && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-3">
            <div className="flex items-center gap-2 text-xs text-green-600 mb-1"><Receipt className="h-3.5 w-3.5" /> Tax Collected</div>
            <p className="text-lg font-bold text-green-700">{formatCurrency(summary.total_tax_collected)}</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-3">
            <div className="flex items-center gap-2 text-xs text-red-600 mb-1"><Receipt className="h-3.5 w-3.5" /> Tax Paid</div>
            <p className="text-lg font-bold text-red-700">{formatCurrency(summary.total_tax_paid)}</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-3">
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1"><Receipt className="h-3.5 w-3.5" /> Net Tax</div>
            <p className={`text-lg font-bold ${summary.total_tax_collected - summary.total_tax_paid >= 0 ? 'text-orange-600' : 'text-blue-600'}`}>
              {formatCurrency(summary.total_tax_collected - summary.total_tax_paid)}
              <span className="text-xs font-normal text-gray-400 ml-1">{summary.total_tax_collected - summary.total_tax_paid >= 0 ? '(owed)' : '(refund)'}</span>
            </p>
          </div>
        </div>
      )}

      {/* Entries Table */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
            <tr>
              <th className="w-10 px-3 py-3">
                <input type="checkbox" checked={selectedIds.size === entries.length && entries.length > 0} onChange={toggleSelectAll} className="rounded border-gray-300" />
              </th>
              <th className="w-8 px-1 py-3 text-xs font-medium text-gray-500 uppercase" title="Status">St</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase">Date</th>
              {activeAccountId === 'all' && <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase">Account</th>}
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase">Description</th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-500 uppercase">Category</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase">Income</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase">Expense</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase">Tax</th>
              <th className="text-right px-3 py-3 text-xs font-medium text-gray-500 uppercase">Balance</th>
              <th className="w-20 px-2 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-gray-800">
            {entriesLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}><td colSpan={11} className="px-4 py-3"><div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" /></td></tr>
              ))
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-4 py-12 text-center">
                  <BookOpen className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 font-medium">No entries found</p>
                </td>
              </tr>
            ) : entries.map(entry => {
              const StatusIcon = STATUS_ICONS[entry.status] || Circle
              const statusColor = STATUS_COLORS[entry.status] || 'text-gray-400'
              return (
                <tr key={entry.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800 ${selectedIds.has(entry.id) ? 'bg-blue-50 dark:bg-blue-950/20' : ''} ${entry.is_deleted ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(entry.id)} onChange={() => toggleSelect(entry.id)} className="rounded border-gray-300" />
                  </td>
                  <td className="px-1 py-2.5" title={entry.status}><StatusIcon className={`w-4 h-4 ${statusColor}`} /></td>
                  <td className="px-3 py-2.5 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">{formatDate(entry.date)}</td>
                  {activeAccountId === 'all' && (
                    <td className="px-3 py-2.5">
                      <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                        {entry.account_name || accountMap.get(entry.account_id)?.name || '?'}
                      </span>
                    </td>
                  )}
                  <td className="px-3 py-2.5">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{entry.description}</p>
                    {entry.notes && <p className="text-xs text-gray-500 truncate max-w-[200px]">{entry.notes}</p>}
                  </td>
                  <td className="px-3 py-2.5">
                    {entry.category ? (
                      <span className="inline-block px-2 py-0.5 text-xs rounded-full" style={{ backgroundColor: entry.category.color ? `${entry.category.color}20` : '#f3f4f6', color: entry.category.color || '#6b7280' }}>
                        {entry.category.name}
                      </span>
                    ) : <span className="text-xs text-gray-400">—</span>}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-right">
                    {entry.entry_type === 'income' ? <span className="font-medium text-green-700">{formatCurrency(entry.total_amount)}</span> : <span className="text-gray-300">-</span>}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-right">
                    {entry.entry_type === 'expense' ? <span className="font-medium text-red-700">{formatCurrency(entry.total_amount)}</span> : <span className="text-gray-300">-</span>}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-right text-gray-600 dark:text-gray-400">
                    {entry.tax_amount != null && entry.tax_amount > 0 ? formatCurrency(entry.tax_amount) : '-'}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-right font-medium">
                    {entry.bank_balance != null ? (
                      <span className={entry.bank_balance >= 0 ? 'text-gray-900 dark:text-gray-100' : 'text-red-700'}>
                        {entry.bank_balance < 0 ? '-' : ''}{formatCurrency(entry.bank_balance)}
                      </span>
                    ) : <span className="text-gray-400">-</span>}
                  </td>
                  <td className="px-2 py-2.5" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center gap-0.5 justify-end">
                      <button onClick={() => setEditEntry(entry)} className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950 rounded" title="Edit">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setSplitEntryTarget(entry)} className="p-1 text-gray-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950 rounded" title="Split">
                        <Scissors className="w-3.5 h-3.5" />
                      </button>
                      {entry.is_deleted && (
                        <button onClick={() => restoreMutation.mutate(entry.id)} className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 dark:hover:bg-green-950 rounded" title="Restore">
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">{currentPage}/{totalPages} ({meta?.total_count} total)</p>
          <div className="flex gap-1">
            <button disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)} className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 dark:text-gray-300">Prev</button>
            <button disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)} className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 dark:text-gray-300">Next</button>
          </div>
        </div>
      )}

      {/* Category Totals */}
      {summary && categoryTotals.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700">
          <button onClick={() => setShowCategoryTotals(!showCategoryTotals)} className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            Category Totals
            <ChevronDown className={`h-4 w-4 transition-transform ${showCategoryTotals ? 'rotate-180' : ''}`} />
          </button>
          {showCategoryTotals && (
            <div className="px-4 pb-4">
              {incomeTotals.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-xs font-semibold text-green-700 uppercase mb-2">Income</h4>
                  {incomeTotals.map((ct: any) => (
                    <div key={`i-${ct.category_id}`} className="flex justify-between text-sm py-1">
                      <span className="text-gray-700 dark:text-gray-300">{ct.category_name} <span className="text-gray-400">({ct.count})</span></span>
                      <span className="text-green-700 font-medium">{formatCurrency(ct.total_amount)}</span>
                    </div>
                  ))}
                </div>
              )}
              {expenseTotals.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-red-700 uppercase mb-2">Expenses</h4>
                  {expenseTotals.map((ct: any) => (
                    <div key={`e-${ct.category_id}`} className="flex justify-between text-sm py-1">
                      <span className="text-gray-700 dark:text-gray-300">{ct.category_name} <span className="text-gray-400">({ct.count})</span></span>
                      <span className="text-red-700 font-medium">{formatCurrency(ct.total_amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Dialogs */}
      <ExcelImportDialog isOpen={showImportDialog} onClose={() => setShowImportDialog(false)} accounts={accounts} onImported={() => { queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] }); queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] }) }} />
      {editEntry && <EditEntryModal entry={editEntry} onClose={() => setEditEntry(null)} />}
      {splitEntryTarget && <SplitEntryModal entry={splitEntryTarget} onClose={() => setSplitEntryTarget(null)} />}
    </div>
  )
}
