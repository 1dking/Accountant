import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { triggerExtraction, getExtraction } from '@/api/ai'
import type { ReceiptExtraction } from '@/api/ai'
import { Sparkles, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

interface ExtractionResultsProps {
  documentId: string
  mimeType: string
  canExtract: boolean
}

const CATEGORY_LABELS: Record<string, string> = {
  food_dining: 'Food & Dining',
  transportation: 'Transportation',
  office_supplies: 'Office Supplies',
  travel: 'Travel',
  utilities: 'Utilities',
  insurance: 'Insurance',
  professional_services: 'Professional Services',
  software_subscriptions: 'Software & Subscriptions',
  marketing: 'Marketing',
  equipment: 'Equipment',
  taxes: 'Taxes',
  entertainment: 'Entertainment',
  healthcare: 'Healthcare',
  education: 'Education',
  other: 'Other',
}

function formatCurrency(amount: number | null, currency: string = 'USD'): string {
  if (amount === null || amount === undefined) return '-'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

function formatPaymentMethod(method: string | null): string {
  if (!method) return '-'
  return method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function ExtractionResults({ documentId, mimeType, canExtract }: ExtractionResultsProps) {
  const queryClient = useQueryClient()
  const [showLineItems, setShowLineItems] = useState(false)
  const [showFullText, setShowFullText] = useState(false)

  const extractable = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'application/pdf'].includes(mimeType)

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['extraction', documentId],
    queryFn: () => getExtraction(documentId),
    enabled: !!documentId,
  })

  const extractMutation = useMutation({
    mutationFn: () => triggerExtraction(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['extraction', documentId] })
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
    },
  })

  const status = statusData?.data
  const extraction = status?.extraction

  if (!extractable) return null

  if (statusLoading) {
    return (
      <div className="py-2">
        <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
      </div>
    )
  }

  // No extraction yet -- show extract button
  if (!status?.has_extraction) {
    if (!canExtract) return null
    return (
      <div>
        <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">AI Extraction</label>
        <button
          onClick={() => extractMutation.mutate()}
          disabled={extractMutation.isPending}
          className="mt-1 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 disabled:opacity-50 transition-colors"
        >
          {extractMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Extracting...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Extract Data with AI
            </>
          )}
        </button>
        {extractMutation.isError && (
          <p className="mt-1 text-xs text-red-600">
            {(extractMutation.error as Error).message || 'Extraction failed'}
          </p>
        )}
      </div>
    )
  }

  // Show extraction results
  return (
    <ExtractionDisplay
      extraction={extraction!}
      showLineItems={showLineItems}
      setShowLineItems={setShowLineItems}
      showFullText={showFullText}
      setShowFullText={setShowFullText}
      canExtract={canExtract}
      onReExtract={() => extractMutation.mutate()}
      isReExtracting={extractMutation.isPending}
    />
  )
}

function ExtractionDisplay({
  extraction,
  showLineItems,
  setShowLineItems,
  showFullText,
  setShowFullText,
  canExtract,
  onReExtract,
  isReExtracting,
}: {
  extraction: ReceiptExtraction
  showLineItems: boolean
  setShowLineItems: (v: boolean) => void
  showFullText: boolean
  setShowFullText: (v: boolean) => void
  canExtract: boolean
  onReExtract: () => void
  isReExtracting: boolean
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-purple-500" />
          AI Extracted Data
        </label>
        {canExtract && (
          <button
            onClick={onReExtract}
            disabled={isReExtracting}
            className="text-xs text-purple-600 hover:text-purple-700 disabled:opacity-50"
          >
            {isReExtracting ? 'Re-extracting...' : 'Re-extract'}
          </button>
        )}
      </div>

      <div className="mt-1 space-y-2 text-sm">
        {/* Vendor */}
        {extraction.vendor_name && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Vendor</span>
            <span className="text-gray-900 dark:text-gray-100 font-medium">{extraction.vendor_name}</span>
          </div>
        )}

        {/* Date */}
        {extraction.date && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Date</span>
            <span className="text-gray-900 dark:text-gray-100">{extraction.date}</span>
          </div>
        )}

        {/* Total */}
        {extraction.total_amount != null && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Total</span>
            <span className="text-gray-900 dark:text-gray-100 font-bold">
              {formatCurrency(extraction.total_amount, extraction.currency)}
            </span>
          </div>
        )}

        {/* Subtotal + Tax */}
        {extraction.subtotal != null && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Subtotal</span>
            <span className="text-gray-700 dark:text-gray-300">{formatCurrency(extraction.subtotal, extraction.currency)}</span>
          </div>
        )}
        {extraction.tax_amount != null && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Tax{extraction.tax_rate != null ? ` (${extraction.tax_rate}%)` : ''}</span>
            <span className="text-gray-700 dark:text-gray-300">{formatCurrency(extraction.tax_amount, extraction.currency)}</span>
          </div>
        )}
        {extraction.tip_amount != null && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Tip</span>
            <span className="text-gray-700 dark:text-gray-300">{formatCurrency(extraction.tip_amount, extraction.currency)}</span>
          </div>
        )}

        {/* Payment method */}
        {extraction.payment_method && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Payment</span>
            <span className="text-gray-700 dark:text-gray-300">{formatPaymentMethod(extraction.payment_method)}</span>
          </div>
        )}

        {/* Category */}
        {extraction.category && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Category</span>
            <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-purple-50 text-purple-700">
              {CATEGORY_LABELS[extraction.category] || extraction.category}
            </span>
          </div>
        )}

        {/* Receipt number */}
        {extraction.receipt_number && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Receipt #</span>
            <span className="text-gray-700 dark:text-gray-300 font-mono text-xs">{extraction.receipt_number}</span>
          </div>
        )}

        {/* Line items */}
        {extraction.line_items.length > 0 && (
          <div>
            <button
              onClick={() => setShowLineItems(!showLineItems)}
              className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700"
            >
              {showLineItems ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {extraction.line_items.length} line item{extraction.line_items.length !== 1 ? 's' : ''}
            </button>
            {showLineItems && (
              <div className="mt-1 border rounded-md overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 dark:bg-gray-950">
                    <tr>
                      <th className="text-left px-2 py-1 text-gray-500 dark:text-gray-400 font-medium">Item</th>
                      <th className="text-right px-2 py-1 text-gray-500 dark:text-gray-400 font-medium">Qty</th>
                      <th className="text-right px-2 py-1 text-gray-500 dark:text-gray-400 font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extraction.line_items.map((item, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-2 py-1 text-gray-700 dark:text-gray-300">{item.description}</td>
                        <td className="px-2 py-1 text-right text-gray-500 dark:text-gray-400">{item.quantity ?? '-'}</td>
                        <td className="px-2 py-1 text-right text-gray-700 dark:text-gray-300">
                          {item.total != null ? formatCurrency(item.total, extraction.currency) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Full OCR text */}
        {extraction.full_text && (
          <div>
            <button
              onClick={() => setShowFullText(!showFullText)}
              className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700"
            >
              {showFullText ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              Full OCR text
            </button>
            {showFullText && (
              <pre className="mt-1 p-2 bg-gray-50 dark:bg-gray-950 border rounded-md text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap max-h-48 overflow-y-auto">
                {extraction.full_text}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
