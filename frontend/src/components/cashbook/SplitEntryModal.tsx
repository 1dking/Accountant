import { useState } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { X, Loader2, Plus, Trash2, Scissors } from 'lucide-react'
import { splitEntry, listCategories } from '@/api/cashbook'
import type { CashbookEntry, TransactionCategory } from '@/types/models'
import { toast } from 'sonner'

interface SplitEntryModalProps {
  entry: CashbookEntry
  onClose: () => void
}

interface SplitLine {
  description: string
  amount: string
  category_id: string
  notes: string
}

export default function SplitEntryModal({ entry, onClose }: SplitEntryModalProps) {
  const queryClient = useQueryClient()
  const [lines, setLines] = useState<SplitLine[]>([
    { description: '', amount: String(entry.total_amount), category_id: entry.category_id || '', notes: '' },
    { description: '', amount: '0', category_id: '', notes: '' },
  ])

  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const categories: TransactionCategory[] = (categoriesData?.data ?? []).filter(
    (c: TransactionCategory) => c.category_type === entry.entry_type || c.category_type === 'both'
  )

  const total = lines.reduce((sum, l) => sum + (parseFloat(l.amount) || 0), 0)
  const diff = entry.total_amount - total

  const mutation = useMutation({
    mutationFn: () => splitEntry(
      entry.id,
      lines.map(l => ({
        description: l.description,
        amount: parseFloat(l.amount) || 0,
        category_id: l.category_id || undefined,
        notes: l.notes || undefined,
      }))
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      toast.success(`Split into ${lines.length} entries`)
      onClose()
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Split failed')
    },
  })

  const addLine = () => {
    setLines([...lines, { description: '', amount: '0', category_id: '', notes: '' }])
  }

  const removeLine = (index: number) => {
    if (lines.length <= 2) return
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: keyof SplitLine, value: string) => {
    setLines(lines.map((l, i) => i === index ? { ...l, [field]: value } : l))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <Scissors className="w-5 h-5" />
              Split Transaction
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {entry.description} — ${entry.total_amount.toFixed(2)}
            </p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-3">
          {lines.map((line, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-start">
              <div className="col-span-4">
                <input
                  type="text"
                  value={line.description}
                  onChange={e => updateLine(i, 'description', e.target.value)}
                  placeholder="Description"
                  className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
              </div>
              <div className="col-span-2">
                <input
                  type="number"
                  step="0.01"
                  value={line.amount}
                  onChange={e => updateLine(i, 'amount', e.target.value)}
                  placeholder="Amount"
                  className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
              </div>
              <div className="col-span-4">
                <select
                  value={line.category_id}
                  onChange={e => updateLine(i, 'category_id', e.target.value)}
                  className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                >
                  <option value="">Uncategorized</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2 flex gap-1">
                <button
                  onClick={() => removeLine(i)}
                  disabled={lines.length <= 2}
                  className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-950 rounded disabled:opacity-30"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}

          <button
            onClick={addLine}
            className="flex items-center gap-1 text-sm text-blue-600 hover:underline"
          >
            <Plus className="w-3.5 h-3.5" /> Add line
          </button>

          {/* Totals */}
          <div className="flex items-center justify-between pt-3 border-t dark:border-gray-700 text-sm">
            <span className="text-gray-500 dark:text-gray-400">
              Total: <span className="font-medium text-gray-900 dark:text-gray-100">${total.toFixed(2)}</span>
              {' / '}${entry.total_amount.toFixed(2)}
            </span>
            {Math.abs(diff) > 0.001 && (
              <span className="text-red-600 text-xs">
                Difference: ${diff.toFixed(2)}
              </span>
            )}
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
            disabled={
              mutation.isPending ||
              Math.abs(diff) > 0.001 ||
              lines.some(l => !l.description || parseFloat(l.amount) <= 0)
            }
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scissors className="w-4 h-4" />}
            Split
          </button>
        </div>
      </div>
    </div>
  )
}
