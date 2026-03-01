import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listExpenses, listCategories } from '@/api/accounting'
import CategoryBadge from '@/components/expenses/CategoryBadge'
import { useAuthStore } from '@/stores/authStore'
import { formatDate } from '@/lib/utils'
import { EXPENSE_STATUSES } from '@/lib/constants'
import { Plus, Search, Filter, Receipt, TrendingUp } from 'lucide-react'
import type { ExpenseFilters } from '@/types/models'

function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

export default function ExpensesPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'admin' || user?.role === 'accountant'

  const [filters, setFilters] = useState<ExpenseFilters>({
    page: 1,
    page_size: 20,
  })
  const [searchInput, setSearchInput] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const { data: expensesData, isLoading } = useQuery({
    queryKey: ['expenses', filters],
    queryFn: () => listExpenses(filters),
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['expense-categories'],
    queryFn: () => listCategories(),
  })

  const expenses = expensesData?.data ?? []
  const meta = expensesData?.meta
  const categories = categoriesData?.data ?? []

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, search: searchInput || undefined, page: 1 }))
  }

  const totalPages = meta?.total_pages ?? 1
  const currentPage = meta?.page ?? 1

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Expenses</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {meta?.total_count ?? 0} total expenses
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/expenses/dashboard')}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <TrendingUp className="h-4 w-4" />
            Dashboard
          </button>
          {canEdit && (
            <button
              onClick={() => navigate('/expenses/new')}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              New Expense
            </button>
          )}
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex gap-2">
        <div className="flex-1 flex gap-2">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search expenses..."
              className="w-full pl-10 pr-4 py-2 text-sm border dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <button onClick={handleSearch} className="px-4 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300">
            Search
          </button>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 px-4 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
        >
          <Filter className="h-4 w-4" />
          Filters
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="bg-gray-50 dark:bg-gray-950 rounded-lg p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Category</label>
            <select
              value={filters.category_id || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, category_id: e.target.value || undefined, page: 1 }))}
              className="w-full mt-1 px-2 py-1.5 text-sm border dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 dark:text-gray-100"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Status</label>
            <select
              value={filters.status || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value || undefined, page: 1 }))}
              className="w-full mt-1 px-2 py-1.5 text-sm border dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 dark:text-gray-100"
            >
              <option value="">All statuses</option>
              {EXPENSE_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Date From</label>
            <input
              type="date"
              value={filters.date_from || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value || undefined, page: 1 }))}
              className="w-full mt-1 px-2 py-1.5 text-sm border dark:border-gray-600 rounded-md dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Date To</label>
            <input
              type="date"
              value={filters.date_to || ''}
              onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value || undefined, page: 1 }))}
              className="w-full mt-1 px-2 py-1.5 text-sm border dark:border-gray-600 rounded-md dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
        </div>
      )}

      {/* Expenses table */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Date</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Vendor</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Category</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Amount</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Receipt</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={6} className="px-4 py-3">
                    <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                  </td>
                </tr>
              ))
            ) : expenses.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <Receipt className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 dark:text-gray-400 font-medium">No expenses found</p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                    {canEdit ? 'Upload a receipt and create your first expense' : 'No expenses have been recorded yet'}
                  </p>
                </td>
              </tr>
            ) : (
              expenses.map((expense) => {
                const statusInfo = EXPENSE_STATUSES.find((s) => s.value === expense.status)
                return (
                  <tr
                    key={expense.id}
                    onClick={() => navigate(`/expenses/${expense.id}`)}
                    className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                  >
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatDate(expense.date)}</td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{expense.vendor_name || 'Unknown vendor'}</p>
                      {expense.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">{expense.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <CategoryBadge category={expense.category} />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100 text-right">
                      {formatCurrency(expense.amount, expense.currency)}
                    </td>
                    <td className="px-4 py-3">
                      {statusInfo && (
                        <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {expense.document_id ? (
                        <span className="text-xs text-green-600">Attached</span>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">None</span>
                      )}
                    </td>
                  </tr>
                )
              })
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
              onClick={() => setFilters((prev) => ({ ...prev, page: currentPage - 1 }))}
              className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
            >
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setFilters((prev) => ({ ...prev, page: currentPage + 1 }))}
              className="px-3 py-1 text-sm border dark:border-gray-600 rounded-md disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800 dark:text-gray-300"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
