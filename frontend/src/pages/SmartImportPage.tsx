import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload, FileImage, CheckCircle2,
  Loader2, ArrowRight, FileText,
  Pencil, Trash2, X, Check, AlertTriangle,
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

export default function SmartImportPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [activeImport, setActiveImport] = useState<(SmartImport & { items: SmartImportItem[] }) | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [itemOverrides, setItemOverrides] = useState<Record<string, Partial<SmartImportItem>>>({})
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<{ description: string; amount: string; date: string }>({ description: '', amount: '', date: '' })

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

  const handleFile = useCallback((file: File) => {
    uploadMutation.mutate(file)
  }, [uploadMutation])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

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
      // Remove from local state
      setActiveImport((prev) => {
        if (!prev) return prev
        const updatedItems = prev.items.filter((i) => i.id !== itemId)
        if (updatedItems.length === 0) return null // go back to upload view
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Review Import</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {activeImport.original_filename} · {activeImport.ai_summary}
            </p>
          </div>
          <button
            onClick={() => { setActiveImport(null); setSelectedItems(new Set()); setEditingItemId(null) }}
            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Back
          </button>
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
                <th className="px-4 py-3 w-20"></th>
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
                            onClick={(e) => { e.stopPropagation(); startEditing(item) }}
                            className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
                            title="Edit"
                          >
                            <Pencil className="h-3.5 w-3.5" />
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
        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
            <div>
              <p className="text-lg font-medium text-gray-900 dark:text-gray-100">Analyzing document...</p>
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
                Drop a file here or click to browse
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Supports images (PNG, JPEG, WebP) and PDF files up to 20MB
              </p>
            </div>
            <label className="cursor-pointer">
              <input
                type="file"
                className="hidden"
                accept="image/*,.pdf"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleFile(file)
                  e.target.value = ''
                }}
              />
              <span className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition">
                <FileImage className="h-4 w-4" />
                Choose File
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
