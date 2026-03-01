import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listAccounts } from '@/api/cashbook'
import { cashbookCapture } from '@/api/cashbook'
import type { CashbookCaptureResult } from '@/api/cashbook'
import { uploadDocuments } from '@/api/documents'
import { formatFileSize } from '@/lib/utils'
import {
  X,
  TrendingUp,
  TrendingDown,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'

interface UploadBookingDialogProps {
  isOpen: boolean
  files: File[]
  folderId?: string
  onClose: () => void
  onComplete: () => void
}

interface FileResult {
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  error?: string
  captureResult?: CashbookCaptureResult
}

type BookingType = 'expense' | 'income' | 'other' | null

export default function UploadBookingDialog({
  isOpen,
  files,
  folderId,
  onClose,
  onComplete,
}: UploadBookingDialogProps) {
  const navigate = useNavigate()
  const [step, setStep] = useState<'select_type' | 'processing' | 'results'>(
    'select_type'
  )
  const [bookingType, setBookingType] = useState<BookingType>(null)
  const [accountId, setAccountId] = useState('')
  const [results, setResults] = useState<FileResult[]>([])

  // Fetch accounts for the selector
  const { data: accountsData } = useQuery({
    queryKey: ['cashbook-accounts'],
    queryFn: () => listAccounts(),
    enabled: isOpen,
  })
  const accounts = accountsData?.data ?? []

  // Auto-select if only one account
  useEffect(() => {
    if (accounts.length === 1 && !accountId) {
      setAccountId(accounts[0].id)
    }
  }, [accounts, accountId])

  // Reset state when dialog opens with new files
  useEffect(() => {
    if (isOpen && files.length > 0) {
      setStep('select_type')
      setBookingType(null)
      setResults([])
    }
  }, [isOpen, files])

  if (!isOpen || files.length === 0) return null

  const canSubmit =
    bookingType === 'other' || (bookingType && accountId)

  const handleUpload = async () => {
    if (!bookingType) return

    setStep('processing')
    const fileResults: FileResult[] = files.map((f) => ({
      file: f,
      status: 'pending' as const,
    }))
    setResults(fileResults)

    if (bookingType === 'other') {
      // Use existing upload flow
      setResults((prev) =>
        prev.map((r) => ({ ...r, status: 'uploading' as const }))
      )
      try {
        await uploadDocuments(files, folderId)
        setResults((prev) =>
          prev.map((r) => ({ ...r, status: 'done' as const }))
        )
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed'
        setResults((prev) =>
          prev.map((r) => ({
            ...r,
            status: 'error' as const,
            error: msg,
          }))
        )
      }
      setStep('results')
    } else {
      // Upload and book each file
      for (let i = 0; i < files.length; i++) {
        setResults((prev) =>
          prev.map((r, idx) =>
            idx === i ? { ...r, status: 'uploading' as const } : r
          )
        )

        try {
          const response = await cashbookCapture(
            files[i],
            bookingType,
            accountId,
            folderId
          )
          setResults((prev) =>
            prev.map((r, idx) =>
              idx === i
                ? {
                    ...r,
                    status: 'done' as const,
                    captureResult: response.data,
                  }
                : r
            )
          )
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Upload failed'
          setResults((prev) =>
            prev.map((r, idx) =>
              idx === i
                ? { ...r, status: 'error' as const, error: msg }
                : r
            )
          )
        }
      }
      setStep('results')
    }
  }

  const successCount = results.filter((r) => r.status === 'done').length
  const entryCount = results.filter(
    (r) => r.captureResult?.entry_id
  ).length

  const handleDone = () => {
    onComplete()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {step === 'select_type' && 'Upload Document'}
            {step === 'processing' && 'Processing...'}
            {step === 'results' && 'Upload Complete'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 rounded"
            disabled={step === 'processing'}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4">
          {/* Step 1: Type Selection */}
          {step === 'select_type' && (
            <div className="space-y-4">
              {/* File list */}
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  {files.length === 1
                    ? '1 file selected'
                    : `${files.length} files selected`}
                </p>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <FileText className="h-4 w-4 text-gray-400 dark:text-gray-500 shrink-0" />
                      <span className="truncate">{f.name}</span>
                      <span className="text-gray-400 dark:text-gray-500 text-xs shrink-0">
                        {formatFileSize(f.size)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Type selection */}
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  What type of document is this?
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setBookingType('expense')}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-colors ${
                      bookingType === 'expense'
                        ? 'border-red-500 bg-red-50 dark:bg-red-900/30 text-red-700'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 text-gray-600'
                    }`}
                  >
                    <TrendingDown className="h-5 w-5" />
                    <span className="text-sm font-medium">Expense</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setBookingType('income')}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-colors ${
                      bookingType === 'income'
                        ? 'border-green-500 bg-green-50 dark:bg-green-900/30 text-green-700'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 text-gray-600'
                    }`}
                  >
                    <TrendingUp className="h-5 w-5" />
                    <span className="text-sm font-medium">Income</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setBookingType('other')}
                    className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-colors ${
                      bookingType === 'other'
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 text-gray-600'
                    }`}
                  >
                    <FileText className="h-5 w-5" />
                    <span className="text-sm font-medium">Other</span>
                  </button>
                </div>
              </div>

              {/* Account selector (for expense/income) */}
              {(bookingType === 'expense' || bookingType === 'income') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Payment Account
                  </label>
                  {accounts.length === 0 ? (
                    <p className="text-sm text-amber-600">
                      No payment accounts found.{' '}
                      <button
                        type="button"
                        onClick={() => {
                          onClose()
                          navigate('/cashbook')
                        }}
                        className="underline hover:no-underline"
                      >
                        Create one in Cashbook
                      </button>
                    </p>
                  ) : (
                    <select
                      value={accountId}
                      onChange={(e) => setAccountId(e.target.value)}
                      className="w-full px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {accounts.length > 1 && (
                        <option value="">Select account...</option>
                      )}
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {bookingType === 'other' && (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Document will be uploaded without creating a cashbook entry.
                </p>
              )}
            </div>
          )}

          {/* Step 2: Processing */}
          {step === 'processing' && (
            <div className="space-y-2">
              {results.map((r, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-950 rounded-md"
                >
                  {r.status === 'pending' && (
                    <div className="h-5 w-5 rounded-full border-2 border-gray-300 dark:border-gray-600" />
                  )}
                  {r.status === 'uploading' && (
                    <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                  )}
                  {r.status === 'done' && (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  )}
                  {r.status === 'error' && (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 dark:text-gray-300 truncate">
                      {r.file.name}
                    </p>
                    {r.status === 'uploading' && (
                      <p className="text-xs text-blue-500">
                        Uploading & processing...
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Step 3: Results */}
          {step === 'results' && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {successCount} of {files.length} file
                {files.length !== 1 ? 's' : ''} uploaded
                {entryCount > 0 &&
                  `, ${entryCount} cashbook entr${entryCount !== 1 ? 'ies' : 'y'} created`}
              </p>

              <div className="space-y-2 max-h-64 overflow-y-auto">
                {results.map((r, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-md border ${
                      r.status === 'done'
                        ? 'bg-green-50 dark:bg-green-900/30 border-green-200'
                        : 'bg-red-50 dark:bg-red-900/30 border-red-200'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {r.status === 'done' ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                          {r.file.name}
                        </p>
                        {r.error && (
                          <p className="text-xs text-red-600 mt-1">
                            {r.error}
                          </p>
                        )}
                        {r.captureResult?.entry_id && (
                          <div className="mt-1 text-xs text-gray-600 dark:text-gray-400 space-y-0.5">
                            {r.captureResult.entry_description && (
                              <p>{r.captureResult.entry_description}</p>
                            )}
                            <p>
                              {r.captureResult.entry_type === 'expense'
                                ? 'Expense'
                                : 'Income'}
                              :{' '}
                              <span className="font-medium">
                                $
                                {r.captureResult.entry_amount?.toLocaleString(
                                  'en-US',
                                  {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                  }
                                )}
                              </span>
                              {r.captureResult.entry_date &&
                                ` on ${r.captureResult.entry_date}`}
                            </p>
                          </div>
                        )}
                        {r.captureResult &&
                          !r.captureResult.entry_id &&
                          r.status === 'done' && (
                            <p className="text-xs text-amber-600 mt-1">
                              Uploaded, but no entry created (AI could not
                              extract amount)
                            </p>
                          )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {entryCount > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    onComplete()
                    navigate('/cashbook')
                  }}
                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                  View in Cashbook
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-4 border-t">
          {step === 'select_type' && (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUpload}
                disabled={!canSubmit}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {bookingType === 'other'
                  ? 'Upload'
                  : 'Upload & Book'}
              </button>
            </>
          )}
          {step === 'results' && (
            <button
              type="button"
              onClick={handleDone}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
