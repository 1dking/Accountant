import { useState } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { X, Loader2, Check } from 'lucide-react'
import { updateEntry, listCategories, listAccounts } from '@/api/cashbook'
import type { CashbookEntry, TransactionCategory, PaymentAccount, EntryStatusType } from '@/types/models'
import { toast } from 'sonner'

interface EditEntryModalProps {
  entry: CashbookEntry
  onClose: () => void
  onSaved?: () => void
}

const STATUS_OPTIONS: { value: EntryStatusType; label: string; color: string }[] = [
  { value: 'pending', label: 'Pending', color: 'text-yellow-600' },
  { value: 'cleared', label: 'Cleared', color: 'text-blue-600' },
  { value: 'reconciled', label: 'Reconciled', color: 'text-green-600' },
  { value: 'voided', label: 'Voided', color: 'text-red-600' },
]

export default function EditEntryModal({ entry, onClose, onSaved }: EditEntryModalProps) {
  const queryClient = useQueryClient()

  const [entryType, setEntryType] = useState(entry.entry_type)
  const [accountId, setAccountId] = useState(entry.account_id)
  const [date, setDate] = useState(entry.date)
  const [description, setDescription] = useState(entry.description)
  const [totalAmount, setTotalAmount] = useState(String(entry.total_amount))
  const [taxAmount, setTaxAmount] = useState(entry.tax_amount != null ? String(entry.tax_amount) : '')
  const [taxOverride, setTaxOverride] = useState(entry.tax_override)
  const [categoryId, setCategoryId] = useState(entry.category_id || '')
  const [notes, setNotes] = useState(entry.notes || '')
  const [status, setStatus] = useState<EntryStatusType>(entry.status || 'pending')

  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const categories: TransactionCategory[] = categoriesData?.data ?? []

  const { data: accountsData } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
  })
  const accounts: PaymentAccount[] = accountsData?.data ?? []

  const filteredCategories = categories.filter(
    c => c.category_type === entryType || c.category_type === 'both'
  )

  const mutation = useMutation({
    mutationFn: () => {
      const data: Record<string, unknown> = {}
      if (entryType !== entry.entry_type) data.entry_type = entryType
      if (accountId !== entry.account_id) data.account_id = accountId
      if (date !== entry.date) data.date = date
      if (description !== entry.description) data.description = description
      const amt = parseFloat(totalAmount)
      if (!isNaN(amt) && amt !== entry.total_amount) data.total_amount = amt
      if (taxOverride !== entry.tax_override) data.tax_override = taxOverride
      if (taxOverride && taxAmount) data.tax_amount = parseFloat(taxAmount)
      if (categoryId !== (entry.category_id || '')) data.category_id = categoryId || null
      if (notes !== (entry.notes || '')) data.notes = notes || null
      if (status !== entry.status) data.status = status
      return updateEntry(entry.id, data as any)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      toast.success('Entry updated')
      onSaved?.()
      onClose()
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to update entry')
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Edit Entry</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
            <div className="flex gap-2">
              {(['income', 'expense'] as const).map(t => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setEntryType(t)}
                  className={`flex-1 px-3 py-2 text-sm rounded-lg border ${
                    entryType === t
                      ? t === 'income'
                        ? 'bg-green-50 dark:bg-green-950 border-green-300 dark:border-green-700 text-green-700 dark:text-green-300'
                        : 'bg-red-50 dark:bg-red-950 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                      : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400'
                  }`}
                >
                  {t === 'income' ? 'Income' : 'Expense'}
                </button>
              ))}
            </div>
          </div>

          {/* Account */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account</label>
            <select
              value={accountId}
              onChange={e => setAccountId(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          {/* Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date</label>
            <input
              type="date"
              value={date}
              onChange={e => setDate(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
          </div>

          {/* Amount */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Total Amount</label>
              <input
                type="number"
                step="0.01"
                value={totalAmount}
                onChange={e => setTotalAmount(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Tax Amount
                <label className="ml-2 inline-flex items-center gap-1 text-xs text-gray-400">
                  <input
                    type="checkbox"
                    checked={taxOverride}
                    onChange={e => setTaxOverride(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  Override
                </label>
              </label>
              <input
                type="number"
                step="0.01"
                value={taxAmount}
                onChange={e => setTaxAmount(e.target.value)}
                disabled={!taxOverride}
                className="w-full px-3 py-2 border rounded-lg text-sm disabled:opacity-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Category</label>
            <select
              value={categoryId}
              onChange={e => setCategoryId(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              <option value="">Uncategorized</option>
              {filteredCategories.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Status</label>
            <select
              value={status}
              onChange={e => setStatus(e.target.value as EntryStatusType)}
              className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              {STATUS_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !description}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            {mutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}
