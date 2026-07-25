import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FileBadge, Loader2, Plus } from 'lucide-react'
import { get1099Report, set1099Flag, type Vendor1099Row } from '@/api/accounting'

function money(n: string): string {
  return parseFloat(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function Tax1099Page() {
  const now = new Date()
  const [year, setYear] = useState(now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear())
  const { data, isLoading } = useQuery({
    queryKey: ['1099-report', year],
    queryFn: () => get1099Report(year),
  })
  const report = data?.data

  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i)

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <FileBadge className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">1099 Contractors</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Year-end totals for contractors you paid, from your bills and cashbook. A 1099-NEC is
            generally owed for anyone paid $600 or more.
          </p>
        </div>
        <select
          value={year}
          onChange={(e) => setYear(parseInt(e.target.value))}
          className="px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
        >
          {years.map((y) => (
            <option key={y} value={y}>Tax year {y}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : !report ? null : (
        <>
          <VendorTable
            title="1099 vendors"
            subtitle="Flagged contractors and what they were paid this year."
            rows={report.vendors}
            year={year}
            emptyText="No contractors flagged for 1099 yet. Flag candidates below, or mark a vendor from their contact record."
          />
          {report.candidates.length > 0 && (
            <VendorTable
              title="Candidates (paid over threshold, not flagged)"
              subtitle="Paid $600+ this year but not marked as a 1099 vendor — flag any that should be reported."
              rows={report.candidates}
              year={year}
              candidate
            />
          )}
        </>
      )}
    </div>
  )
}

function VendorTable({
  title, subtitle, rows, year, candidate, emptyText,
}: {
  title: string
  subtitle: string
  rows: Vendor1099Row[]
  year: number
  candidate?: boolean
  emptyText?: string
}) {
  const queryClient = useQueryClient()
  const flag = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => set1099Flag(id, on),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['1099-report', year] })
      toast.success('Vendor updated')
    },
    onError: (e: any) => toast.error(e?.message || 'Failed to update'),
  })

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{subtitle}</p>
      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 dark:text-gray-400">
            <tr>
              <th className="text-left font-medium px-4 py-2">Vendor</th>
              <th className="text-left font-medium px-4 py-2 hidden sm:table-cell">Tax ID</th>
              <th className="text-right font-medium px-4 py-2 w-32">Total paid</th>
              <th className="text-right font-medium px-4 py-2 w-24"></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400 text-sm">{emptyText}</td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.contact_id} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-4 py-2">
                    <div className="text-gray-900 dark:text-gray-100">{r.name}</div>
                    {r.contact_name && <div className="text-xs text-gray-400">{r.contact_name}</div>}
                  </td>
                  <td className="px-4 py-2 hidden sm:table-cell text-gray-500 dark:text-gray-400 font-mono text-xs">
                    {r.tax_id || <span className="text-amber-500">missing</span>}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    ${money(r.total_paid)}
                    {r.meets_threshold && (
                      <span className="ml-1 text-[10px] text-green-600 dark:text-green-400">1099</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {candidate ? (
                      <button
                        onClick={() => flag.mutate({ id: r.contact_id, on: true })}
                        disabled={flag.isPending}
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950 px-2 py-1 rounded disabled:opacity-50"
                      >
                        <Plus className="w-3.5 h-3.5" /> Flag
                      </button>
                    ) : (
                      <button
                        onClick={() => flag.mutate({ id: r.contact_id, on: false })}
                        disabled={flag.isPending}
                        className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600 px-2 py-1 rounded disabled:opacity-50"
                        title="Remove 1099 flag"
                      >
                        Unflag
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
