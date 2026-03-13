import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload, FileImage, CheckCircle2,
  Loader2, ArrowRight, FileText,
  Pencil, Trash2, X, Check, AlertTriangle,
  Eye, Scissors,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import {
  uploadForImport,
  listImports,
  getImport,
  confirmImport,
  updateImportItem,
  deleteImport,
  deleteImportItem,
  getImportPreviewUrl,
  type SmartImport,
  type SmartImportItem,
} from '@/api/smartImport'
import { listAccounts, listCategories } from '@/api/cashbook'
import type { PaymentAccount } from '@/types/models'

function formatCurrency(amount: number): string {
  return '$' + Math.abs(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'text-green-600 bg-green-50 dark:bg-green-900/30 dark:text-green-400'
    : pct >= 50 ? 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/30 dark:text-yellow-400'
    : 'text-red-600 bg-red-50 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={cn('text-xs font-medium px-1.5 py-0.5 rounded', color)}>
      {pct}%
    </span>
  )
}

/* ── Preview Modal (full-screen document only) ────────── */
function PreviewModal({ importId, filename, mimeType, onClose }: {
  importId: string
  filename: string
  mimeType?: string
  onClose: () => void
}) {
  const url = getImportPreviewUrl(importId)
  const isPdf = mimeType?.includes('pdf') || filename.toLowerCase().endsWith('.pdf')
  const isImage = mimeType?.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(filename)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="relative bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-[90vw] h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{filename}</p>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto flex items-center justify-center bg-gray-100 dark:bg-gray-950 p-4">
          {isPdf ? (
            <iframe src={url} className="w-full h-full rounded border dark:border-gray-700" title="Preview" />
          ) : isImage ? (
            <img src={url} alt={filename} className="max-w-full max-h-full object-contain rounded" />
          ) : (
            <p className="text-gray-500 dark:text-gray-400">Preview not available for this file type.</p>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Split-Screen Edit Modal (PDF left + edit form right) */
function EditPreviewModal({ importId, filename, mimeType, item, overrides, categories, onClose, onSave }: {
  importId: string
  filename: string
  mimeType?: string
  item: SmartImportItem
  overrides?: Partial<SmartImportItem>
  categories: { id: string; name: string }[]
  onClose: () => void
  onSave: (itemId: string, updates: Partial<SmartImportItem>) => void
}) {
  const url = getImportPreviewUrl(importId)
  const isPdf = mimeType?.includes('pdf') || filename.toLowerCase().endsWith('.pdf')
  const isImage = mimeType?.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(filename)

  const [draft, setDraft] = useState({
    entry_type: (overrides?.entry_type ?? item.entry_type) as 'income' | 'expense',
    date: (overrides?.date ?? item.date) || '',
    description: overrides?.description ?? item.description,
    amount: String(overrides?.amount ?? item.amount),
    category_suggestion: overrides?.category_suggestion ?? item.category_suggestion ?? '',
  })

  const handleSave = () => {
    const amount = parseFloat(draft.amount)
    if (isNaN(amount) || amount <= 0) {
      return
    }
    onSave(item.id, {
      entry_type: draft.entry_type,
      date: draft.date || null,
      description: draft.description,
      amount,
      category_suggestion: draft.category_suggestion || null,
    } as Partial<SmartImportItem>)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="relative bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-[95vw] max-w-6xl h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700 shrink-0">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{filename}</p>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Split content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Document preview (60%) */}
          <div className="w-[60%] bg-gray-100 dark:bg-gray-950 p-4 overflow-auto flex items-center justify-center border-r dark:border-gray-700">
            {isPdf ? (
              <iframe src={url} className="w-full h-full rounded border dark:border-gray-700" title="Preview" />
            ) : isImage ? (
              <img src={url} alt={filename} className="max-w-full max-h-full object-contain rounded" />
            ) : (
              <p className="text-gray-500 dark:text-gray-400">Preview not available for this file type.</p>
            )}
          </div>

          {/* Right: Edit form (40%) */}
          <div className="w-[40%] p-6 overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Edit Transaction</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
                <div className="flex gap-2">
                  {(['expense', 'income'] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setDraft(d => ({ ...d, entry_type: t }))}
                      className={cn(
                        'px-4 py-2 text-sm font-medium rounded-lg border transition-colors flex-1',
                        draft.entry_type === t
                          ? t === 'income' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-300 dark:border-green-700'
                            : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-300 dark:border-red-700'
                          : 'bg-white dark:bg-gray-800 text-gray-500 border-gray-200 dark:border-gray-600 hover:border-gray-400',
                      )}
                    >
                      {t === 'income' ? 'Income' : 'Expense'}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date</label>
                <input
                  type="date"
                  value={draft.date}
                  onChange={(e) => setDraft(d => ({ ...d, date: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <input
                  type="text"
                  value={draft.description}
                  onChange={(e) => setDraft(d => ({ ...d, description: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={draft.amount}
                  onChange={(e) => setDraft(d => ({ ...d, amount: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Category</label>
                <select
                  value={draft.category_suggestion}
                  onChange={(e) => setDraft(d => ({ ...d, category_suggestion: e.target.value }))}
                  className="w-full px-3 py-2 text-sm border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">No category</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.name}>{cat.name}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                <span>AI Confidence:</span>
                <ConfidenceBadge value={item.confidence} />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t dark:border-gray-700">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Split Modal ───────────────────────────────────────── */
function SplitModal({ item, onClose, onSplit }: {
  item: SmartImportItem & { overrides?: Partial<SmartImportItem> }
  onClose: () => void
  onSplit: (months: number) => void
}) {
  const [months, setMonths] = useState(12)
  const amount = item.overrides?.amount ?? item.amount
  const perMonth = amount / months

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Split Into Monthly Entries
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Split "{item.overrides?.description ?? item.description}" ({formatCurrency(amount)}) into equal monthly entries.
        </p>

        <div className="grid grid-cols-5 gap-2">
          {[2, 3, 4, 6, 12].map((n) => (
            <button
              key={n}
              onClick={() => setMonths(n)}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-lg border transition-colors',
                months === n
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:border-blue-400',
              )}
            >
              {n}mo
            </button>
          ))}
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            <span className="font-medium">{months} entries</span> × {formatCurrency(perMonth)} each
          </p>
          {amount !== perMonth * months && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Rounding difference of {formatCurrency(Math.abs(amount - perMonth * months))} added to first entry.
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={() => onSplit(months)}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            Split into {months} Entries
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SmartImportPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [activeImport, setActiveImport] = useState<(SmartImport & { items: SmartImportItem[] }) | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [itemOverrides, setItemOverrides] = useState<Record<string, Partial<SmartImportItem>>>({})
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<{ description: string; amount: string; date: string }>({ description: '', amount: '', date: '' })
  const [showPreview, setShowPreview] = useState(false)
  const [editPreviewItem, setEditPreviewItem] = useState<SmartImportItem | null>(null)
  const [splitItem, setSplitItem] = useState<SmartImportItem | null>(null)
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(null)

  const { data: importsData } = useQuery({
    queryKey: ['smart-imports'],
    queryFn: () => listImports(),
  })
  const imports = importsData?.data ?? []

  const { data: accountsData } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
  })
  const accounts: PaymentAccount[] = accountsData?.data ?? []

  const { data: categoriesData } = useQuery({
    queryKey: ['cashbook-categories'],
    queryFn: () => listCategories(),
  })
  const categories = categoriesData?.data ?? []

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadForImport(file),
    onSuccess: (data) => {
      setActiveImport(data.data)
      setSelectedItems(new Set())
      setItemOverrides({})
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
    },
  })

  const batchUploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const results: Array<SmartImport & { items: SmartImportItem[] }> = []
      for (let i = 0; i < files.length; i++) {
        setBatchProgress({ current: i + 1, total: files.length })
        try {
          const resp = await uploadForImport(files[i])
          results.push(resp.data)
        } catch (err: any) {
          toast.error(`Failed: ${files[i].name} — ${err?.message || 'Unknown error'}`)
        }
      }
      setBatchProgress(null)
      return results
    },
    onSuccess: (results) => {
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
      if (results.length === 1) {
        setActiveImport(results[0])
        setSelectedItems(new Set())
        setItemOverrides({})
      } else if (results.length > 1) {
        toast.success(`Processed ${results.length} files. Check recent imports below.`)
      }
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!activeImport || !selectedAccountId) return Promise.reject('No import or account')
      // Push any overrides to the backend before confirming
      const overrideEntries = Object.entries(itemOverrides).filter(
        ([id]) => selectedItems.has(id)
      )
      if (overrideEntries.length > 0) {
        await Promise.all(
          overrideEntries.map(([id, overrides]) => updateImportItem(id, overrides))
        )
      }
      return confirmImport(activeImport.id, selectedAccountId, Array.from(selectedItems))
    },
    onSuccess: (result) => {
      const data = (result as any)?.data
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })

      if (data?.errors?.length > 0) {
        toast.warning(`Imported ${data.imported_count} of ${data.total_items} items. ${data.errors.length} failed.`)
      } else {
        toast.success(`Imported ${data?.imported_count ?? 0} entries into your cashbook.`)
        setActiveImport(null)
        setSelectedItems(new Set())
        setItemOverrides({})
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Import failed. Please try again.')
    },
  })

  const deleteImportMutation = useMutation({
    mutationFn: (importId: string) => deleteImport(importId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      toast.success('Import batch deleted.')
    },
  })

  const handleFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files)
    if (arr.length === 0) return
    if (arr.length === 1) {
      uploadMutation.mutate(arr[0])
    } else {
      batchUploadMutation.mutate(arr)
    }
  }, [uploadMutation, batchUploadMutation])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  const handleLoadImport = async (imp: SmartImport) => {
    try {
      const resp = await getImport(imp.id)
      setActiveImport(resp.data)
      setSelectedItems(new Set())
      setItemOverrides({})
    } catch {
      // Failed to load
    }
  }

  const handleDeleteItem = async (itemId: string) => {
    if (!activeImport) return
    try {
      await deleteImportItem(itemId)
      setActiveImport((prev) => {
        if (!prev) return prev
        const updatedItems = prev.items.filter((i) => i.id !== itemId)
        if (updatedItems.length === 0) return null
        return { ...prev, items: updatedItems, item_count: updatedItems.length }
      })
      setSelectedItems((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
      const { [itemId]: _, ...rest } = itemOverrides
      setItemOverrides(rest)
    } catch {
      toast.error('Failed to delete item')
    }
  }

  const handleSplit = (item: SmartImportItem, months: number) => {
    if (!activeImport) return
    const baseAmount = itemOverrides[item.id]?.amount ?? item.amount
    const baseDesc = itemOverrides[item.id]?.description ?? item.description
    const baseDate = itemOverrides[item.id]?.date ?? item.date
    const perMonth = Math.round((baseAmount / months) * 100) / 100
    const remainder = Math.round((baseAmount - perMonth * months) * 100) / 100

    // Override the original item as month 1
    setItemOverrides((prev) => ({
      ...prev,
      [item.id]: {
        ...prev[item.id],
        description: `${baseDesc} (1/${months})`,
        amount: perMonth + remainder,
        date: baseDate,
      },
    }))

    // Create virtual split entries for months 2+
    const newItems: SmartImportItem[] = []
    for (let i = 1; i < months; i++) {
      let splitDate = baseDate
      if (baseDate) {
        const d = new Date(baseDate + 'T00:00:00')
        d.setMonth(d.getMonth() + i)
        splitDate = d.toISOString().slice(0, 10)
      }
      const splitId = `${item.id}_split_${i}`
      newItems.push({
        ...item,
        id: splitId,
        description: `${baseDesc} (${i + 1}/${months})`,
        amount: perMonth,
        date: splitDate,
        status: 'pending' as any,
        confidence: item.confidence,
      })
    }

    setActiveImport((prev) => {
      if (!prev) return prev
      // Insert new items right after the original
      const idx = prev.items.findIndex((i) => i.id === item.id)
      const items = [...prev.items]
      items.splice(idx + 1, 0, ...newItems)
      return { ...prev, items, item_count: items.length }
    })

    // Auto-select all new split items
    setSelectedItems((prev) => {
      const next = new Set(prev)
      next.add(item.id)
      newItems.forEach((ni) => next.add(ni.id))
      return next
    })

    setSplitItem(null)
    toast.success(`Split into ${months} monthly entries.`)
  }

  const startEditing = (item: SmartImportItem) => {
    setEditingItemId(item.id)
    setEditDraft({
      description: itemOverrides[item.id]?.description ?? item.description,
      amount: String(itemOverrides[item.id]?.amount ?? item.amount),
      date: (itemOverrides[item.id]?.date ?? item.date) || '',
    })
  }

  const saveEditing = () => {
    if (!editingItemId) return
    const amount = parseFloat(editDraft.amount)
    if (isNaN(amount) || amount <= 0) {
      toast.error('Amount must be a positive number')
      return
    }
    setItemOverrides((prev) => ({
      ...prev,
      [editingItemId]: {
        ...prev[editingItemId],
        description: editDraft.description,
        amount,
        date: editDraft.date || null,
      },
    }))
    setEditingItemId(null)
  }

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (!activeImport) return
    const importable = activeImport.items.filter((i) => i.status !== 'imported')
    if (selectedItems.size === importable.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(importable.map((i) => i.id)))
    }
  }

  // Show review table when we have an active import with items
  if (activeImport && activeImport.items && activeImport.items.length > 0) {
    const importableItems = activeImport.items.filter((i) => i.status !== 'imported')
    const importedItems = activeImport.items.filter((i) => i.status === 'imported')
    const allSelected = importableItems.length > 0 && importableItems.every((i) => selectedItems.has(i.id))
    const selectedTotal = activeImport.items
      .filter((i) => selectedItems.has(i.id))
      .reduce((sum, i) => {
        const overriddenAmount = itemOverrides[i.id]?.amount ?? i.amount
        return sum + overriddenAmount
      }, 0)

    const confirmData = (confirmMutation.data as any)?.data

    return (
      <div className="p-6 space-y-4">
        {showPreview && (
          <PreviewModal
            importId={activeImport.id}
            filename={activeImport.original_filename}
            mimeType={activeImport.mime_type}
            onClose={() => setShowPreview(false)}
          />
        )}
        {editPreviewItem && (
          <EditPreviewModal
            importId={activeImport.id}
            filename={activeImport.original_filename}
            mimeType={activeImport.mime_type}
            item={editPreviewItem}
            overrides={itemOverrides[editPreviewItem.id]}
            categories={categories}
            onClose={() => setEditPreviewItem(null)}
            onSave={(itemId, updates) => {
              setItemOverrides((prev) => ({
                ...prev,
                [itemId]: { ...prev[itemId], ...updates },
              }))
            }}
          />
        )}
        {splitItem && (
          <SplitModal
            item={{ ...splitItem, overrides: itemOverrides[splitItem.id] }}
            onClose={() => setSplitItem(null)}
            onSplit={(months) => handleSplit(splitItem, months)}
          />
        )}

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Review Import</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {activeImport.original_filename} · {activeImport.ai_summary}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowPreview(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              title="Preview source document"
            >
              <Eye className="h-4 w-4" />
              Preview
            </button>
            <button
              onClick={() => { setActiveImport(null); setSelectedItems(new Set()); setEditingItemId(null) }}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Back
            </button>
          </div>
        </div>

        {/* Import controls */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Import to Account <span className="text-red-500">*</span>
            </label>
            {accounts.length === 0 ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500 dark:text-gray-400">No accounts yet.</span>
                <button
                  onClick={() => navigate('/cashbook')}
                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline font-medium"
                >
                  Create an account first
                </button>
              </div>
            ) : (
              <select
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                className="w-full max-w-xs px-3 py-2 text-sm border dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
                <option value="">Select account...</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
                ))}
              </select>
            )}
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {selectedItems.size} of {importableItems.length} selected · {formatCurrency(selectedTotal)}
            </p>
            <button
              onClick={() => confirmMutation.mutate()}
              disabled={!selectedAccountId || selectedItems.size === 0 || confirmMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {confirmMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
              Import {selectedItems.size} Item{selectedItems.size !== 1 ? 's' : ''}
            </button>
          </div>
        </div>

        {/* Success / partial success banner */}
        {confirmMutation.isSuccess && confirmData && (
          <div className={cn(
            'rounded-lg p-4 border',
            confirmData.errors?.length > 0
              ? 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
              : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
          )}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                {confirmData.errors?.length > 0 ? (
                  <>
                    <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                    <span className="text-orange-700 dark:text-orange-400">
                      Imported {confirmData.imported_count} of {confirmData.total_items} items.
                    </span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                    <span className="text-green-700 dark:text-green-400">
                      Imported {confirmData.imported_count} entries into {accounts.find(a => a.id === selectedAccountId)?.name || 'your cashbook'}.
                    </span>
                  </>
                )}
              </div>
              <button
                onClick={() => navigate('/cashbook')}
                className="px-3 py-1.5 text-sm font-medium text-blue-700 dark:text-blue-400 border border-blue-300 dark:border-blue-700 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/40"
              >
                View in Cashbook
              </button>
            </div>
            {confirmData.errors?.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-xs font-medium text-orange-700 dark:text-orange-400">Skipped items:</p>
                {confirmData.errors.map((err: string, i: number) => (
                  <p key={i} className="text-xs text-orange-600 dark:text-orange-500 pl-2">- {err}</p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Already imported items summary */}
        {importedItems.length > 0 && importableItems.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
            {importedItems.length} item{importedItems.length !== 1 ? 's' : ''} already imported.
            Showing {importableItems.length} remaining.
          </div>
        )}

        {/* Items table */}
        <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-950 border-b dark:border-gray-700">
              <tr>
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                  />
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Type</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Date</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Description</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Category</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Confidence</th>
                <th className="px-4 py-3 w-24"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {activeImport.items.map((item) => {
                const isEditing = editingItemId === item.id
                const isImported = item.status === 'imported'

                if (isEditing) {
                  return (
                    <tr key={item.id} className="bg-blue-50/50 dark:bg-blue-900/10">
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2">
                        <button
                          type="button"
                          onClick={() => {
                            const currentType = itemOverrides[item.id]?.entry_type ?? item.entry_type
                            const newType = currentType === 'income' ? 'expense' : 'income'
                            setItemOverrides((prev) => ({
                              ...prev,
                              [item.id]: { ...prev[item.id], entry_type: newType },
                            }))
                          }}
                          className={cn(
                            'text-xs font-medium px-2 py-0.5 rounded-full cursor-pointer transition-colors',
                            (itemOverrides[item.id]?.entry_type ?? item.entry_type) === 'income'
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                          )}
                        >
                          {itemOverrides[item.id]?.entry_type ?? item.entry_type}
                        </button>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="date"
                          value={editDraft.date}
                          onChange={(e) => setEditDraft((d) => ({ ...d, date: e.target.value }))}
                          className="text-sm border dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 w-32"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editDraft.description}
                          onChange={(e) => setEditDraft((d) => ({ ...d, description: e.target.value }))}
                          className="text-sm border dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 w-full"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={editDraft.amount}
                          onChange={(e) => setEditDraft((d) => ({ ...d, amount: e.target.value }))}
                          className="text-sm border dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 w-24 text-right"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <select
                          value={itemOverrides[item.id]?.category_suggestion ?? item.category_suggestion ?? ''}
                          onChange={(e) => {
                            setItemOverrides((prev) => ({
                              ...prev,
                              [item.id]: { ...prev[item.id], category_suggestion: e.target.value || null },
                            }))
                          }}
                          className="text-xs bg-transparent border border-gray-200 dark:border-gray-600 rounded px-1.5 py-0.5 text-gray-700 dark:text-gray-300 max-w-[140px]"
                        >
                          <option value="">No category</option>
                          {categories.map((cat) => (
                            <option key={cat.id} value={cat.name}>{cat.name}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={saveEditing}
                            className="p-1 text-green-600 hover:text-green-700 dark:text-green-400"
                            title="Save"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => setEditingItemId(null)}
                            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                            title="Cancel"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                }

                return (
                  <tr
                    key={item.id}
                    onClick={() => !isImported && toggleItem(item.id)}
                    className={cn(
                      'transition-colors cursor-pointer',
                      isImported && 'bg-green-50/50 dark:bg-green-900/10 cursor-default opacity-60',
                      selectedItems.has(item.id) && !isImported && 'bg-blue-50/50 dark:bg-blue-900/10',
                      item.is_duplicate && 'opacity-70',
                    )}
                  >
                    <td className="px-4 py-3">
                      {isImported ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : (
                        <input
                          type="checkbox"
                          checked={selectedItems.has(item.id)}
                          onChange={() => toggleItem(item.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                        />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (isImported) return
                          const currentType = itemOverrides[item.id]?.entry_type ?? item.entry_type
                          const newType = currentType === 'income' ? 'expense' : 'income'
                          setItemOverrides((prev) => ({
                            ...prev,
                            [item.id]: { ...prev[item.id], entry_type: newType },
                          }))
                        }}
                        disabled={isImported}
                        className={cn(
                          'text-xs font-medium px-2 py-0.5 rounded-full transition-colors',
                          !isImported && 'cursor-pointer',
                          (itemOverrides[item.id]?.entry_type ?? item.entry_type) === 'income'
                            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50'
                            : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50'
                        )}
                      >
                        {itemOverrides[item.id]?.entry_type ?? item.entry_type}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {(itemOverrides[item.id]?.date ?? item.date) || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-[200px] truncate">
                      {itemOverrides[item.id]?.description ?? item.description}
                      {item.is_duplicate && (
                        <span className="ml-2 text-[10px] bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 px-1.5 py-0.5 rounded">
                          possible duplicate
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(itemOverrides[item.id]?.amount ?? item.amount)}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={itemOverrides[item.id]?.category_suggestion ?? item.category_suggestion ?? ''}
                        onChange={(e) => {
                          e.stopPropagation()
                          setItemOverrides((prev) => ({
                            ...prev,
                            [item.id]: { ...prev[item.id], category_suggestion: e.target.value || null },
                          }))
                        }}
                        onClick={(e) => e.stopPropagation()}
                        disabled={isImported}
                        className="text-xs bg-transparent border border-gray-200 dark:border-gray-600 rounded px-1.5 py-0.5 text-gray-700 dark:text-gray-300 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 max-w-[140px]"
                      >
                        <option value="">No category</option>
                        {categories.map((cat) => (
                          <option key={cat.id} value={cat.name}>{cat.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ConfidenceBadge value={item.confidence} />
                    </td>
                    <td className="px-4 py-3">
                      {!isImported && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => { e.stopPropagation(); setEditPreviewItem(item) }}
                            className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                            title="Edit with preview"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); setSplitItem(item) }}
                            className="p-1 text-gray-400 hover:text-purple-600 dark:hover:text-purple-400"
                            title="Split into monthly entries"
                          >
                            <Scissors className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDeleteItem(item.id) }}
                            className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400"
                            title="Remove"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // Upload / processing / history view
  const isUploading = uploadMutation.isPending || batchUploadMutation.isPending

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Smart Import</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Upload receipts, invoices, or bank statements. AI extracts the transactions for you.
        </p>
      </div>

      {/* Upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'relative bg-white dark:bg-gray-900 rounded-xl border-2 border-dashed p-12 text-center transition-colors',
          isDragging ? 'border-blue-400 bg-blue-50/50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700',
        )}
      >
        {isUploading ? (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
            <div>
              <p className="text-lg font-medium text-gray-900 dark:text-gray-100">
                {batchProgress
                  ? `Processing file ${batchProgress.current} of ${batchProgress.total}...`
                  : 'Analyzing document...'}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">AI is extracting transactions. This may take a moment.</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className="h-16 w-16 bg-blue-50 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
              <Upload className="h-8 w-8 text-blue-500" />
            </div>
            <div>
              <p className="text-lg font-medium text-gray-900 dark:text-gray-100">
                Drop files here or click to browse
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Supports images (PNG, JPEG, WebP) and PDF files up to 20MB. Select multiple files for batch upload.
              </p>
            </div>
            <label className="cursor-pointer">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept="image/*,.pdf"
                multiple
                onChange={(e) => {
                  const files = e.target.files
                  if (files && files.length > 0) handleFiles(files)
                  e.target.value = ''
                }}
              />
              <span className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition">
                <FileImage className="h-4 w-4" />
                Choose Files
              </span>
            </label>
          </div>
        )}

        {uploadMutation.isError && (
          <p className="text-sm text-red-600 mt-4">
            {(uploadMutation.error as Error).message || 'Upload failed. Please try again.'}
          </p>
        )}
      </div>

      {/* Recent imports */}
      {imports.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Recent Imports</h2>
          <div className="bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 divide-y dark:divide-gray-700">
            {imports.map((imp) => (
              <div
                key={imp.id}
                className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <button
                  onClick={() => handleLoadImport(imp)}
                  className="flex-1 flex items-center gap-4 text-left min-w-0"
                >
                  <FileText className="h-5 w-5 text-gray-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {imp.original_filename}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {imp.ai_summary || imp.document_type || 'Processing...'}
                      {' · '}{imp.item_count} item{imp.item_count !== 1 ? 's' : ''}
                      {' · '}{new Date(imp.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={cn(
                    'text-xs font-medium px-2 py-0.5 rounded-full shrink-0',
                    imp.status === 'ready' && 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
                    imp.status === 'imported' && 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                    imp.status === 'processing' && 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
                    imp.status === 'failed' && 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
                    imp.status === 'partially_imported' && 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400',
                  )}>
                    {imp.status === 'partially_imported' ? 'partial' : imp.status}
                  </span>
                </button>
                <button
                  onClick={() => {
                    if (confirm('Delete this import batch' + (imp.status === 'imported' || imp.status === 'partially_imported' ? ' and its cashbook entries' : '') + '?')) {
                      deleteImportMutation.mutate(imp.id)
                    }
                  }}
                  className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 shrink-0"
                  title="Delete import"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
