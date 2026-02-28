import { useQuery } from '@tanstack/react-query'
import { BookOpen, ExternalLink } from 'lucide-react'
import { useNavigate } from 'react-router'
import { api } from '@/api/client'
import { formatDate } from '@/lib/utils'

interface CashbookLinkProps {
  source: 'expense' | 'income'
  sourceId: string
}

function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

export default function CashbookLink({ source, sourceId }: CashbookLinkProps) {
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['cashbook-entry-by-source', source, sourceId],
    queryFn: () =>
      api.get<{
        data: {
          id: string
          account_id: string
          entry_type: string
          date: string
          description: string
          total_amount: number
          account_name?: string
        } | null
      }>(`/cashbook/entries/by-source?source=${source}&source_id=${sourceId}`),
    enabled: !!sourceId,
  })

  if (isLoading) {
    return (
      <div className="bg-gray-50 border rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
    )
  }

  const entry = data?.data ?? null

  if (!entry) {
    return (
      <div className="bg-gray-50 border rounded-lg p-4">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <BookOpen className="h-4 w-4" />
          <span>Not booked to cashbook</span>
        </div>
        <button
          onClick={() => navigate('/cashbook/new')}
          className="mt-2 text-sm text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-1"
        >
          Book to cashbook
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>
    )
  }

  return (
    <div className="bg-gray-50 border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="h-4 w-4 text-gray-600" />
        <h3 className="text-sm font-semibold text-gray-900">Cashbook Entry</h3>
      </div>

      <div className="space-y-2 text-sm">
        {entry.account_name && (
          <div className="flex justify-between">
            <span className="text-gray-500">Account</span>
            <span className="text-gray-900 font-medium">{entry.account_name}</span>
          </div>
        )}

        <div className="flex justify-between items-center">
          <span className="text-gray-500">Type</span>
          <span
            className={`inline-block px-2 py-0.5 text-xs rounded-full font-medium ${
              entry.entry_type === 'income'
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {entry.entry_type === 'income' ? 'Income' : 'Expense'}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500">Amount</span>
          <span className="text-gray-900 font-medium">{formatCurrency(entry.total_amount)}</span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500">Date</span>
          <span className="text-gray-900">{formatDate(entry.date)}</span>
        </div>
      </div>

      <button
        onClick={() => navigate(`/cashbook/entries/${entry.id}`)}
        className="mt-3 w-full flex items-center justify-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium py-1.5 rounded-md hover:bg-blue-50 transition-colors"
      >
        View in Cashbook
        <ExternalLink className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
