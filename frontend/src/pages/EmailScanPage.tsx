import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import {
  Inbox, Download, RefreshCw, FileText, CheckCircle, Trash2, Search,
  ChevronLeft, ChevronRight, X, ArrowRight, Calendar, Filter, Repeat,
  Eye, Paperclip,
} from 'lucide-react'
import {
  listGmailAccounts,
  listGmailScanResults,
  scanGmailEmails,
  parseEmailForImport,
  importEmailFull,
  deleteGmailScanResult,
  bulkDeleteGmailScanResults,
  getAttachmentPreview,
} from '@/api/integrations'
import { listCategories } from '@/api/accounting'
import { listAccounts as listCashbookAccounts } from '@/api/cashbook'
import { formatDate } from '@/lib/utils'
import type { GmailScanResult, EmailParsedData, ExpenseCategory, PaymentAccount } from '@/types/models'

// ---------------------------------------------------------------------------
// Import Confirmation Modal
// ---------------------------------------------------------------------------

function addFrequency(dateStr: string, freq: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  if (freq === 'weekly') d.setDate(d.getDate() + 7)
  else if (freq === 'monthly') d.setMonth(d.getMonth() + 1)
  else if (freq === 'quarterly') d.setMonth(d.getMonth() + 3)
  else if (freq === 'yearly') d.setFullYear(d.getFullYear() + 1)
  return d.toISOString().split('T')[0]
}

function ImportModal({
  result,
  parsedData,
  categories,
  cashbookAccounts,
  onConfirm,
  onCancel,
  isPending,
}: {
  result: GmailScanResult
  parsedData: EmailParsedData | null
  categories: ExpenseCategory[]
  cashbookAccounts: PaymentAccount[]
  onConfirm: (data: {
    record_type: 'expense' | 'income'
    vendor_name: string
    description: string
    amount: number | null
    currency: string
    date: string
    category_id: string | null
    income_category: string
    notes: string
    account_id: string | null
    is_recurring: boolean
    recurring_frequency: string | null
    recurring_next_date: string | null
  }) => void
  onCancel: () => void
  isPending: boolean
}) {
  const navigate = useNavigate()
  const [recordType, setRecordType] = useState<'expense' | 'income'>(
    parsedData?.record_type || 'expense'
  )
  const [vendorName, setVendorName] = useState(parsedData?.vendor_name || '')
  const [description, setDescription] = useState(
    parsedData?.description || result.subject || ''
  )
  const [amount, setAmount] = useState(parsedData?.amount || '')
  const [currency, setCurrency] = useState(parsedData?.currency || 'USD')
  const [date, setDate] = useState(
    parsedData?.date || (result.date ? result.date.split('T')[0] : new Date().toISOString().split('T')[0])
  )
  const [categoryId, setCategoryId] = useState('')
  const [incomeCategory, setIncomeCategory] = useState('other')
  const [notes, setNotes] = useState('')
  const [accountId, setAccountId] = useState(cashbookAccounts.length === 1 ? cashbookAccounts[0].id : '')
  const [isRecurring, setIsRecurring] = useState(false)
  const [recurringFrequency, setRecurringFrequency] = useState('monthly')
  const [recurringNextDate, setRecurringNextDate] = useState('')

  // Preview state
  const [previewTab, setPreviewTab] = useState<'email' | 'attachment'>('email')
  const [attachmentData, setAttachmentData] = useState<{ content_base64: string; mimeType: string; filename: string } | null>(null)
  const [loadingAttachment, setLoadingAttachment] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const attachments = parsedData?.attachments ?? []

  // Load PDF attachment for preview
  const loadAttachment = useCallback(async (index: number) => {
    setLoadingAttachment(true)
    try {
      const res = await getAttachmentPreview(result.id, index)
      const att = res.data
      // Gmail returns URL-safe base64, convert to standard base64
      const standardBase64 = att.content_base64.replace(/-/g, '+').replace(/_/g, '/')
      setAttachmentData({ content_base64: standardBase64, mimeType: att.mimeType, filename: att.filename })
      setPreviewTab('attachment')
    } catch {
      toast.error('Failed to load attachment preview')
    } finally {
      setLoadingAttachment(false)
    }
  }, [result.id])

  // Write email HTML into sandboxed iframe
  useEffect(() => {
    if (previewTab === 'email' && iframeRef.current && parsedData?.body_html) {
      const doc = iframeRef.current.contentDocument
      if (doc) {
        doc.open()
        doc.write(`
          <!DOCTYPE html>
          <html><head>
            <meta charset="utf-8">
            <style>body{font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#333;margin:16px;line-height:1.5}img{max-width:100%;height:auto}a{color:#2563eb}</style>
          </head><body>${parsedData.body_html}</body></html>
        `)
        doc.close()
      }
    }
  }, [previewTab, parsedData?.body_html])

  // Try to match suggested category to an actual category
  const suggestedCat = parsedData?.category_suggestion
  const matchedCategory = suggestedCat
    ? categories.find(c => c.name.toLowerCase().includes(suggestedCat.toLowerCase()))
    : null

  if (matchedCategory && !categoryId) {
    setCategoryId(matchedCategory.id)
  }

  const handleRecurringToggle = (on: boolean) => {
    setIsRecurring(on)
    if (on && date && !recurringNextDate) {
      setRecurringNextDate(addFrequency(date, recurringFrequency))
    }
  }

  const handleFrequencyChange = (freq: string) => {
    setRecurringFrequency(freq)
    if (date) {
      setRecurringNextDate(addFrequency(date, freq))
    }
  }

  const canImport = !!accountId && cashbookAccounts.length > 0

  const inputCls = "w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-6xl mx-4 max-h-[92vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b dark:border-gray-700 shrink-0">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">{result.subject || 'Import Email'}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">From: {result.sender}</p>
          </div>
          <button onClick={onCancel} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded ml-3">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Split-screen body */}
        <div className="flex flex-1 overflow-hidden">
          {/* LEFT — Email / Attachment Preview (60%) */}
          <div className="w-3/5 border-r dark:border-gray-700 flex flex-col">
            {/* Preview tabs */}
            <div className="flex items-center gap-1 px-3 py-2 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 shrink-0">
              <button
                onClick={() => setPreviewTab('email')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md ${
                  previewTab === 'email' ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-gray-100' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Eye className="w-3.5 h-3.5" /> Email
              </button>
              {attachments.length > 0 && attachments.map((att, i) => (
                <button
                  key={i}
                  onClick={() => {
                    if (attachmentData && attachmentData.filename === att.filename) {
                      setPreviewTab('attachment')
                    } else {
                      loadAttachment(i)
                    }
                  }}
                  disabled={loadingAttachment}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md ${
                    previewTab === 'attachment' && attachmentData?.filename === att.filename ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-gray-100' : 'text-gray-500 hover:text-gray-700'
                  } disabled:opacity-50`}
                >
                  <Paperclip className="w-3.5 h-3.5" />
                  <span className="truncate max-w-[120px]">{att.filename}</span>
                  <span className="text-gray-400">({(att.size / 1024).toFixed(0)}KB)</span>
                </button>
              ))}
            </div>

            {/* Preview content */}
            <div className="flex-1 overflow-auto bg-white dark:bg-gray-950">
              {previewTab === 'email' ? (
                parsedData?.body_html ? (
                  <iframe
                    ref={iframeRef}
                    sandbox="allow-same-origin"
                    title="Email preview"
                    className="w-full h-full border-0"
                  />
                ) : parsedData?.body_text ? (
                  <pre className="p-4 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-sans">{parsedData.body_text}</pre>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                    <div className="text-center">
                      <Eye className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p>No email preview available</p>
                      <p className="text-xs mt-1">Re-scan to capture email content</p>
                    </div>
                  </div>
                )
              ) : (
                loadingAttachment ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
                  </div>
                ) : attachmentData ? (
                  attachmentData.mimeType === 'application/pdf' ? (
                    <iframe
                      src={`data:application/pdf;base64,${attachmentData.content_base64}`}
                      title={attachmentData.filename}
                      className="w-full h-full border-0"
                    />
                  ) : attachmentData.mimeType.startsWith('image/') ? (
                    <div className="flex items-center justify-center h-full p-4">
                      <img
                        src={`data:${attachmentData.mimeType};base64,${attachmentData.content_base64}`}
                        alt={attachmentData.filename}
                        className="max-w-full max-h-full object-contain"
                      />
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                      <div className="text-center">
                        <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        <p>{attachmentData.filename}</p>
                        <p className="text-xs mt-1">Preview not available for this file type</p>
                      </div>
                    </div>
                  )
                ) : null
              )}
            </div>
          </div>

          {/* RIGHT — Import Form (40%) */}
          <div className="w-2/5 flex flex-col">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Record type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setRecordType('expense')}
                    className={`flex-1 px-3 py-2 text-sm rounded-lg border ${
                      recordType === 'expense'
                        ? 'bg-red-50 dark:bg-red-950 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Expense
                  </button>
                  <button
                    onClick={() => setRecordType('income')}
                    className={`flex-1 px-3 py-2 text-sm rounded-lg border ${
                      recordType === 'income'
                        ? 'bg-green-50 dark:bg-green-950 border-green-300 dark:border-green-700 text-green-700 dark:text-green-300'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Income
                  </button>
                </div>
              </div>

              {/* Account */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Account <span className="text-red-500">*</span>
                </label>
                {cashbookAccounts.length === 0 ? (
                  <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
                    <span className="text-sm text-amber-700 dark:text-amber-400">No accounts yet.</span>
                    <button onClick={() => { onCancel(); navigate('/cashbook') }} className="text-sm text-blue-600 dark:text-blue-400 hover:underline font-medium">
                      Create an account first
                    </button>
                  </div>
                ) : (
                  <select value={accountId} onChange={e => setAccountId(e.target.value)} className={inputCls}>
                    <option value="">Select account...</option>
                    {cashbookAccounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Vendor */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {recordType === 'expense' ? 'Vendor' : 'Source'}
                </label>
                <input type="text" value={vendorName} onChange={e => setVendorName(e.target.value)} className={inputCls} placeholder={parsedData?.vendor_name || 'Enter vendor name...'} />
                {suggestedCat && (
                  <p className="text-xs text-gray-400 mt-1">Suggested category: <span className="text-blue-500">{suggestedCat}</span></p>
                )}
              </div>

              {/* Amount + Currency */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount</label>
                  <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} className={inputCls} placeholder="0.00" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Currency</label>
                  <select value={currency} onChange={e => setCurrency(e.target.value)} className={inputCls}>
                    <option value="CAD">CAD</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </div>
              </div>

              {/* Date */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} className={inputCls} />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <input type="text" value={description} onChange={e => setDescription(e.target.value)} className={inputCls} />
              </div>

              {/* Category */}
              {recordType === 'expense' ? (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Category</label>
                  <select value={categoryId} onChange={e => setCategoryId(e.target.value)} className={inputCls}>
                    <option value="">Uncategorized</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Income Category</label>
                  <select value={incomeCategory} onChange={e => setIncomeCategory(e.target.value)} className={inputCls}>
                    <option value="service">Service</option>
                    <option value="product">Product</option>
                    <option value="invoice_payment">Invoice Payment</option>
                    <option value="interest">Interest</option>
                    <option value="refund">Refund</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              )}

              {/* Recurring toggle */}
              <div className="border dark:border-gray-700 rounded-lg p-3 space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Repeat className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Recurring bill?</span>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={isRecurring}
                    onClick={() => handleRecurringToggle(!isRecurring)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${
                      isRecurring ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                      isRecurring ? 'translate-x-5' : ''
                    }`} />
                  </button>
                </label>
                {isRecurring && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Frequency</label>
                      <select value={recurringFrequency} onChange={e => handleFrequencyChange(e.target.value)} className={inputCls}>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                        <option value="yearly">Yearly</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Next Due Date</label>
                      <input type="date" value={recurringNextDate} onChange={e => setRecurringNextDate(e.target.value)} className={inputCls} />
                    </div>
                  </div>
                )}
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className={inputCls + ' resize-none'} placeholder="Optional notes..." />
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700 shrink-0">
              <button onClick={onCancel} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                Cancel
              </button>
              <button
                onClick={() => onConfirm({
                  record_type: recordType,
                  vendor_name: vendorName,
                  description: description || 'Imported from email',
                  amount: amount ? parseFloat(String(amount)) : null,
                  currency,
                  date,
                  category_id: categoryId || null,
                  income_category: incomeCategory,
                  notes,
                  account_id: accountId || null,
                  is_recurring: isRecurring,
                  recurring_frequency: isRecurring ? recurringFrequency : null,
                  recurring_next_date: isRecurring ? recurringNextDate : null,
                })}
                disabled={isPending || !canImport}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                {isPending ? 'Importing...' : 'Import'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Delete Confirmation Modal
// ---------------------------------------------------------------------------

function DeleteConfirmModal({
  count,
  onConfirm,
  onCancel,
  isPending,
}: {
  count: number
  onConfirm: () => void
  onCancel: () => void
  isPending: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-sm mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Remove {count === 1 ? 'email' : `${count} emails`} from inbox?
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            This only removes {count === 1 ? 'it' : 'them'} from the accounting inbox, not from Gmail.
          </p>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            {isPending ? 'Removing...' : 'Remove'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function EmailScanPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // Filters
  const [selectedAccount, setSelectedAccount] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('has:attachment (invoice OR receipt OR payment)')
  const [searchFilter, setSearchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'imported'>('all')
  const [afterDate, setAfterDate] = useState('')
  const [beforeDate, setBeforeDate] = useState('')
  const [page, setPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Modals
  const [importTarget, setImportTarget] = useState<GmailScanResult | null>(null)
  const [parsedData, setParsedData] = useState<EmailParsedData | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<'single' | 'bulk' | null>(null)
  const [deleteId, setDeleteId] = useState<string>('')

  // Scanning state
  const [scanPageToken, setScanPageToken] = useState<string | null>(null)
  const [scanCount, setScanCount] = useState(0)

  const { data: accountsData } = useQuery({
    queryKey: ['gmail-accounts'],
    queryFn: listGmailAccounts,
  })

  const resultFilters = {
    gmail_account_id: selectedAccount || undefined,
    is_processed: statusFilter === 'pending' ? false : statusFilter === 'imported' ? true : undefined,
    search: searchFilter || undefined,
    page,
    page_size: 50,
  }

  const { data: resultsData, isLoading: resultsLoading } = useQuery({
    queryKey: ['gmail-results', resultFilters],
    queryFn: () => listGmailScanResults(resultFilters),
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['expense-categories'],
    queryFn: listCategories,
  })

  const { data: cashbookAccountsData } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: listCashbookAccounts,
  })

  const accounts = accountsData?.data ?? []
  const results: GmailScanResult[] = resultsData?.data ?? []
  const meta = resultsData?.meta ?? { total: 0, page: 1, page_size: 50, total_pages: 1 }
  const categories: ExpenseCategory[] = (categoriesData as any)?.data ?? []
  const cashbookAccounts: PaymentAccount[] = (cashbookAccountsData as any)?.data ?? []

  // Scan mutation
  const scanMutation = useMutation({
    mutationFn: (pageToken: string | undefined) => scanGmailEmails({
      gmail_account_id: selectedAccount,
      query: searchQuery,
      max_results: 50,
      after_date: afterDate || undefined,
      before_date: beforeDate || undefined,
      page_token: pageToken || undefined,
    }),
    onSuccess: (data) => {
      const newCount = data.data?.length ?? 0
      setScanCount(prev => prev + newCount)
      const nextToken = data.meta?.next_page_token ?? null
      setScanPageToken(nextToken)
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
      if (newCount > 0) {
        toast.success(`Found ${newCount} new emails`)
      } else {
        toast.info('No new emails found')
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Scan failed')
    },
  })

  // Parse email mutation
  const parseMutation = useMutation({
    mutationFn: parseEmailForImport,
    onSuccess: (data, resultId) => {
      const target = results.find(r => r.id === resultId)
      if (target) {
        setParsedData(data.data)
        setImportTarget(target)
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to parse email')
    },
  })

  // Full import mutation
  const importMutation = useMutation({
    mutationFn: ({ resultId, data }: { resultId: string; data: any }) =>
      importEmailFull(resultId, data),
    onSuccess: (data) => {
      setImportTarget(null)
      setParsedData(null)
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      queryClient.invalidateQueries({ queryKey: ['cashbook-summary'] })

      const result = data.data
      const hasRecurring = !!(result as any).recurring_rule_id
      const label = hasRecurring ? 'Imported + recurring rule created' : 'Imported'

      if (result.expense_id) {
        toast.success(`${label} as expense`, {
          action: {
            label: 'View',
            onClick: () => navigate(`/expenses/${result.expense_id}`),
          },
        })
      } else if (result.income_id) {
        toast.success(`${label} as income`, {
          action: {
            label: 'View',
            onClick: () => navigate('/income'),
          },
        })
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Import failed')
    },
  })

  // Delete mutations
  const deleteMutation = useMutation({
    mutationFn: deleteGmailScanResult,
    onSuccess: () => {
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
      toast.success('Email removed from inbox')
    },
  })

  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => bulkDeleteGmailScanResults(ids),
    onSuccess: (data) => {
      setDeleteTarget(null)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['gmail-results'] })
      toast.success(`Removed ${data.data.deleted} emails from inbox`)
    },
  })

  // Selection handlers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(results.map(r => r.id)))
    }
  }, [results, selectedIds.size])

  const handleImportClick = (result: GmailScanResult) => {
    parseMutation.mutate(result.id)
  }

  const handleImportConfirm = (data: any) => {
    if (!importTarget) return
    importMutation.mutate({ resultId: importTarget.id, data })
  }

  const handleStartScan = () => {
    setScanCount(0)
    setScanPageToken(null)
    scanMutation.mutate(undefined)
  }

  const handleLoadMore = () => {
    if (scanPageToken) {
      scanMutation.mutate(scanPageToken)
    }
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Email Inbox</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">
            Scan Gmail for invoices, receipts, and attachments — import directly as expenses or income
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <button
              onClick={() => setDeleteTarget('bulk')}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              <Trash2 className="w-4 h-4" />
              Delete {selectedIds.size}
            </button>
          )}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg ${
              showFilters
                ? 'bg-blue-50 dark:bg-blue-950 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                : 'hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>
      </div>

      {/* Scan Controls */}
      <div className="bg-white dark:bg-gray-900 border rounded-lg p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={selectedAccount}
            onChange={(e) => { setSelectedAccount(e.target.value); setPage(1) }}
            className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.email}</option>
            ))}
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Gmail search query..."
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
          />
          <button
            onClick={handleStartScan}
            disabled={!selectedAccount || scanMutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${scanMutation.isPending ? 'animate-spin' : ''}`} />
            {scanMutation.isPending ? 'Scanning...' : 'Scan Now'}
          </button>
        </div>

        {/* Date range */}
        {showFilters && (
          <div className="flex flex-wrap gap-3 pt-2 border-t">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={afterDate}
                onChange={e => setAfterDate(e.target.value)}
                className="px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700"
                placeholder="From"
              />
              <span className="text-gray-400 text-sm">to</span>
              <input
                type="date"
                value={beforeDate}
                onChange={e => setBeforeDate(e.target.value)}
                className="px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700"
                placeholder="To"
              />
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <div className="relative">
                <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-gray-400" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={e => { setSearchFilter(e.target.value); setPage(1) }}
                  placeholder="Filter results..."
                  className="pl-8 pr-3 py-1.5 border rounded text-sm w-48 dark:bg-gray-800 dark:border-gray-700"
                />
              </div>
              <select
                value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value as any); setPage(1) }}
                className="px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-700"
              >
                <option value="all">All status</option>
                <option value="pending">Pending</option>
                <option value="imported">Imported</option>
              </select>
            </div>
          </div>
        )}

        {!selectedAccount && accounts.length > 0 && (
          <p className="text-xs text-gray-400 dark:text-gray-500">Select a Gmail account to start scanning.</p>
        )}
        {accounts.length === 0 && (
          <p className="text-xs text-amber-600">
            No Gmail accounts connected. Go to Settings &gt; Gmail to connect one.
          </p>
        )}

        {/* Scan progress */}
        {scanMutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
            <RefreshCw className="w-4 h-4 animate-spin" />
            Scanning... found {scanCount} emails so far
          </div>
        )}
        {scanPageToken && !scanMutation.isPending && (
          <div className="flex items-center gap-3">
            <p className="text-sm text-gray-500">Found {scanCount} new emails. More results available.</p>
            <button
              onClick={handleLoadMore}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-950"
            >
              Load More <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {resultsLoading ? (
        <p className="text-gray-400 dark:text-gray-500 py-8 text-center text-sm">Loading results...</p>
      ) : results.length > 0 ? (
        <>
          <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 dark:bg-gray-950">
                  <th className="w-10 px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === results.length && results.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300"
                    />
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Subject</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">From</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Date</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Attachments</th>
                  <th className="text-left px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                  <th className="text-right px-4 py-3 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr
                    key={result.id}
                    className={`border-b hover:bg-gray-50 dark:hover:bg-gray-800 ${
                      selectedIds.has(result.id) ? 'bg-blue-50 dark:bg-blue-950/30' : ''
                    }`}
                  >
                    <td className="px-3 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(result.id)}
                        onChange={() => toggleSelect(result.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-xs">
                        {result.subject || '(No subject)'}
                      </div>
                      {result.snippet && (
                        <div className="text-xs text-gray-400 dark:text-gray-500 truncate max-w-xs mt-0.5">
                          {result.snippet}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 truncate max-w-[180px]">
                      {result.sender || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {result.date ? formatDate(result.date) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {result.has_attachments ? (
                        <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 text-xs">
                          <FileText className="w-3.5 h-3.5" /> Yes
                        </span>
                      ) : (
                        <span className="text-gray-400 dark:text-gray-500 text-xs">No</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {result.is_processed ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <CheckCircle className="w-3.5 h-3.5" /> Imported
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">Pending</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        {!result.is_processed && (
                          <button
                            onClick={() => handleImportClick(result)}
                            disabled={parseMutation.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                            title="Import as expense or income"
                          >
                            <Download className="w-3 h-3" />
                            Import
                          </button>
                        )}
                        {result.is_processed && (result.matched_expense_id || result.matched_income_id) && (
                          <button
                            onClick={() => {
                              if (result.matched_expense_id) navigate(`/expenses/${result.matched_expense_id}`)
                              else navigate('/income')
                            }}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-green-600 border border-green-300 rounded hover:bg-green-50 dark:hover:bg-green-950"
                          >
                            <ArrowRight className="w-3 h-3" />
                            View
                          </button>
                        )}
                        <button
                          onClick={() => { setDeleteId(result.id); setDeleteTarget('single') }}
                          className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950 rounded"
                          title="Remove from inbox"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {meta.total_pages > 1 && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <p>
                Showing {(meta.page - 1) * meta.page_size + 1}–{Math.min(meta.page * meta.page_size, meta.total)} of {meta.total}
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-2">Page {meta.page} of {meta.total_pages}</span>
                <button
                  onClick={() => setPage(p => Math.min(meta.total_pages, p + 1))}
                  disabled={page >= meta.total_pages}
                  className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <Inbox className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No scan results yet.</p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
            Select a Gmail account and click "Scan Now" to search for invoices and receipts.
          </p>
        </div>
      )}

      {/* Import Modal */}
      {importTarget && (
        <ImportModal
          result={importTarget}
          parsedData={parsedData}
          categories={categories}
          cashbookAccounts={cashbookAccounts}
          onConfirm={handleImportConfirm}
          onCancel={() => { setImportTarget(null); setParsedData(null) }}
          isPending={importMutation.isPending}
        />
      )}

      {/* Delete Confirmation */}
      {deleteTarget === 'single' && (
        <DeleteConfirmModal
          count={1}
          onConfirm={() => deleteMutation.mutate(deleteId)}
          onCancel={() => setDeleteTarget(null)}
          isPending={deleteMutation.isPending}
        />
      )}
      {deleteTarget === 'bulk' && (
        <DeleteConfirmModal
          count={selectedIds.size}
          onConfirm={() => bulkDeleteMutation.mutate(Array.from(selectedIds))}
          onCancel={() => setDeleteTarget(null)}
          isPending={bulkDeleteMutation.isPending}
        />
      )}
    </div>
  )
}
