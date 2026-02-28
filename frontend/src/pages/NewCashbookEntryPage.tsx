import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listAccounts, listCategories, createEntry } from '@/api/cashbook'
import { ArrowLeft } from 'lucide-react'
import type { EntryType } from '@/types/models'

function formatCurrency(amount: number): string {
  return (
    '$' +
    Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  )
}

export default function NewCashbookEntryPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [accountId, setAccountId] = useState('')
  const [entryType, setEntryType] = useState<EntryType>('expense')
  const [entryDate, setEntryDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [notes, setNotes] = useState('')
  const [taxOverride, setTaxOverride] = useState(false)
  const [manualTax, setManualTax] = useState('')

  // Fetch accounts
  const { data: accountsData } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
  })
  const accounts = accountsData?.data ?? []

  // Auto-select first account if none selected
  const activeAccountId = accountId || (accounts.length > 0 ? accounts[0].id : '')

  // Fetch categories
  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const allCategories = categoriesData?.data ?? []

  // Filter categories by entry type
  const filteredCategories = useMemo(() => {
    return allCategories.filter(
      (c) => c.category_type === entryType || c.category_type === 'both'
    )
  }, [allCategories, entryType])

  // Calculate tax: tax = total - (total / 1.13)
  const parsedAmount = parseFloat(amount) || 0
  const calculatedTax =
    parsedAmount > 0
      ? parseFloat((parsedAmount - parsedAmount / 1.13).toFixed(2))
      : 0

  const displayTax = taxOverride
    ? parseFloat(manualTax) || 0
    : calculatedTax

  // Create mutation
  const createMutation = useMutation({
    mutationFn: () =>
      createEntry({
        account_id: activeAccountId,
        entry_type: entryType,
        date: entryDate,
        description,
        total_amount: parsedAmount,
        tax_amount: displayTax > 0 ? displayTax : undefined,
        tax_override: taxOverride,
        category_id: categoryId || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-accounts'] })
      navigate('/cashbook')
    },
  })

  const isValid =
    activeAccountId && description && parsedAmount > 0 && entryDate

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <button
        onClick={() => navigate('/cashbook')}
        className="flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to cashbook
      </button>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        New Cashbook Entry
      </h1>

      <div className="bg-white rounded-lg border p-6 space-y-4">
        {/* Account Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Account <span className="text-red-500">*</span>
          </label>
          <select
            value={activeAccountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="w-full px-3 py-2 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {accounts.length === 0 && (
              <option value="">No accounts available</option>
            )}
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>

        {/* Entry Type Toggle */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type
          </label>
          <div className="flex rounded-md border overflow-hidden">
            <button
              type="button"
              onClick={() => {
                setEntryType('income')
                setCategoryId('')
              }}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                entryType === 'income'
                  ? 'bg-green-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Income
            </button>
            <button
              type="button"
              onClick={() => {
                setEntryType('expense')
                setCategoryId('')
              }}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors border-l ${
                entryType === 'expense'
                  ? 'bg-red-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Expense
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={entryDate}
              onChange={(e) => setEntryDate(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Amount <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this transaction for?"
            className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="w-full px-3 py-2 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a category</option>
            {filteredCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Tax Auto-split */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm font-medium text-gray-700">
              Tax (HST 13%)
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
              <input
                type="checkbox"
                checked={taxOverride}
                onChange={(e) => {
                  setTaxOverride(e.target.checked)
                  if (e.target.checked) {
                    setManualTax(calculatedTax.toFixed(2))
                  }
                }}
                className="rounded border-gray-300"
              />
              Override
            </label>
          </div>
          {taxOverride ? (
            <input
              type="number"
              step="0.01"
              min="0"
              value={manualTax}
              onChange={(e) => setManualTax(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          ) : (
            <div className="w-full px-3 py-2 text-sm border rounded-md bg-gray-50 text-gray-700">
              {parsedAmount > 0 ? formatCurrency(calculatedTax) : '$0.00'}
              {parsedAmount > 0 && (
                <span className="text-xs text-gray-400 ml-2">
                  (auto-calculated from {formatCurrency(parsedAmount)})
                </span>
              )}
            </div>
          )}
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Additional notes..."
            className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={() => navigate('/cashbook')}
            className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!isValid || createMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Saving...' : 'Save Entry'}
          </button>
        </div>

        {createMutation.isError && (
          <p className="text-sm text-red-600">
            {(createMutation.error as Error).message ||
              'Failed to create entry'}
          </p>
        )}
      </div>
    </div>
  )
}
