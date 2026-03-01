import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getEntry, deleteEntry } from '@/api/cashbook'
import { useAuthStore } from '@/stores/authStore'
import { formatDate } from '@/lib/utils'
import { ArrowLeft, FileText, Trash2 } from 'lucide-react'

function formatAmount(amount: number): string {
  return `$${amount.toFixed(2)}`
}

export default function CashbookEntryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canDelete = user?.role === 'admin' || user?.role === 'accountant'

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cashbook-entry', id],
    queryFn: () => getEntry(id!),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteEntry(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashbook-entries'] })
      navigate('/cashbook')
    },
  })

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24" />
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    )
  }

  if (isError || !data?.data) {
    return (
      <div className="p-6 text-center">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Entry not found</h2>
        <button
          onClick={() => navigate('/cashbook')}
          className="mt-2 text-blue-600 dark:text-blue-400 hover:underline"
        >
          Back to cashbook
        </button>
      </div>
    )
  }

  const entry = data.data

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Back link */}
      <div>
        <button
          onClick={() => navigate('/cashbook')}
          className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline mb-3"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to cashbook
        </button>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              {entry.description}
            </h1>
            <div className="mt-1">
              <span
                className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${
                  entry.entry_type === 'income'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {entry.entry_type === 'income' ? 'Income' : 'Expense'}
              </span>
            </div>
          </div>
          <div className="text-right">
            <p
              className={`text-3xl font-bold ${
                entry.entry_type === 'income' ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {entry.entry_type === 'income' ? '+' : '-'}
              {formatAmount(entry.total_amount)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-gray-900 rounded-lg border p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Details</h3>
              <div className="flex gap-2">
                {canDelete && (
                  <button
                    onClick={() => {
                      if (confirm('Delete this cashbook entry?'))
                        deleteMutation.mutate()
                    }}
                    className="flex items-center gap-1 text-sm text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Date</span>
                <p className="text-gray-900 dark:text-gray-100 font-medium">
                  {formatDate(entry.date)}
                </p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Amount</span>
                <p className="text-gray-900 dark:text-gray-100 font-medium">
                  {formatAmount(entry.total_amount)}
                </p>
              </div>
              {entry.tax_amount != null && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Tax</span>
                  <p className="text-gray-900 dark:text-gray-100">
                    {formatAmount(entry.tax_amount)}
                  </p>
                </div>
              )}
              <div>
                <span className="text-gray-500 dark:text-gray-400">Category</span>
                <p className="text-gray-900 dark:text-gray-100">
                  {entry.category?.name ?? 'Uncategorized'}
                </p>
              </div>
              {entry.notes && (
                <div className="col-span-2">
                  <span className="text-gray-500 dark:text-gray-400">Notes</span>
                  <p className="text-gray-700 dark:text-gray-300">{entry.notes}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {entry.document_id && (
            <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm mb-2">
                Linked Document
              </h3>
              <button
                onClick={() => navigate(`/documents/${entry.document_id}`)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-md hover:bg-blue-100"
              >
                <FileText className="h-4 w-4" />
                View Document
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
