import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload, FileImage, CheckCircle2,
  Loader2, ArrowRight, FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  uploadForImport,
  listImports,
  getImport,
  confirmImport,
  type SmartImport,
  type SmartImportItem,
} from '@/api/smartImport'
import { listAccounts } from '@/api/cashbook'
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
  const [activeImport, setActiveImport] = useState<(SmartImport & { items: SmartImportItem[] }) | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())

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

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadForImport(file),
    onSuccess: (data) => {
      setActiveImport(data.data)
      // Auto-select all non-duplicate items
      const ids = new Set(
        (data.data.items || [])
          .filter((i: SmartImportItem) => !i.is_duplicate && i.status !== 'rejected')
          .map((i: SmartImportItem) => i.id)
      )
      setSelectedItems(ids)
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: () => {
      if (!activeImport || !selectedAccountId) return Promise.reject('No import or account')
      return confirmImport(activeImport.id, selectedAccountId, Array.from(selectedItems))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['smart-imports'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })
      setActiveImport(null)
      setSelectedItems(new Set())
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
      // Auto-select all importable items
      const ids = new Set(
        (resp.data.items || [])
          .filter((i: SmartImportItem) => !i.is_duplicate && i.status !== 'rejected' && i.status !== 'imported')
          .map((i: SmartImportItem) => i.id)
      )
      setSelectedItems(ids)
    } catch {
      // Failed to load
    }
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
    const allSelected = importableItems.length > 0 && importableItems.every((i) => selectedItems.has(i.id))
    const selectedTotal = activeImport.items
      .filter((i) => selectedItems.has(i.id))
      .reduce((sum, i) => sum + i.amount, 0)

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
            onClick={() => { setActiveImport(null); setSelectedItems(new Set()) }}
            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Back
          </button>
        </div>

        {/* Import controls */}
        <div className="flex items-center gap-4 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 p-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Import to Account
            </label>
            <select
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
              className="w-full max-w-xs px-3 py-2 text-sm border dark:border-gray-600 rounded-md bg-white dark:bg-gray-800"
            >
              <option value="">Select account...</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {selectedItems.size} of {activeImport.items.length} selected · {formatCurrency(selectedTotal)}
            </p>
            <button
              onClick={() => confirmMutation.mutate()}
              disabled={!selectedAccountId || selectedItems.size === 0 || confirmMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
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

        {confirmMutation.isSuccess && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-sm text-green-700 dark:text-green-400">
            <CheckCircle2 className="h-4 w-4 inline mr-2" />
            Successfully imported {(confirmMutation.data as any)?.data?.imported_count} entries to your cashbook.
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
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {activeImport.items.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => item.status !== 'imported' && toggleItem(item.id)}
                  className={cn(
                    'transition-colors cursor-pointer',
                    item.status === 'imported' && 'bg-green-50/50 dark:bg-green-900/10 cursor-default',
                    selectedItems.has(item.id) && item.status !== 'imported' && 'bg-blue-50/50 dark:bg-blue-900/10',
                    item.is_duplicate && 'opacity-70',
                  )}
                >
                  <td className="px-4 py-3">
                    {item.status === 'imported' ? (
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
                    <span className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      item.entry_type === 'income'
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                        : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                    )}>
                      {item.entry_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                    {item.date || '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-[200px] truncate">
                    {item.description}
                    {item.is_duplicate && (
                      <span className="ml-2 text-[10px] bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 px-1.5 py-0.5 rounded">
                        possible duplicate
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-900 dark:text-gray-100">
                    {formatCurrency(item.amount)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                    {item.category_suggestion || '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ConfidenceBadge value={item.confidence} />
                  </td>
                </tr>
              ))}
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
              <button
                key={imp.id}
                onClick={() => handleLoadImport(imp)}
                className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
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
                  'text-xs font-medium px-2 py-0.5 rounded-full',
                  imp.status === 'ready' && 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
                  imp.status === 'imported' && 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                  imp.status === 'processing' && 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
                  imp.status === 'failed' && 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
                  imp.status === 'partially_imported' && 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400',
                )}>
                  {imp.status}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
