import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Lock, Unlock, CalendarDays } from 'lucide-react'
import { listPeriods, closePeriod, reopenPeriod } from '@/api/accounting'
import type { AccountingPeriod } from '@/types/models'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function PeriodSettings() {
  const queryClient = useQueryClient()
  const [msg, setMsg] = useState('')
  const [closeYear, setCloseYear] = useState(new Date().getFullYear())
  const [closeMonth, setCloseMonth] = useState(new Date().getMonth() + 1)
  const [closeNotes, setCloseNotes] = useState('')
  const [reopenNotes, setReopenNotes] = useState('')
  const [reopenId, setReopenId] = useState<string | null>(null)

  const showMsg = (text: string) => {
    setMsg(text)
    setTimeout(() => setMsg(''), 4000)
  }

  const periodsQuery = useQuery({
    queryKey: ['accounting-periods'],
    queryFn: listPeriods,
  })

  const closeMutation = useMutation({
    mutationFn: () => closePeriod({ year: closeYear, month: closeMonth, notes: closeNotes || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounting-periods'] })
      setCloseNotes('')
      showMsg(`Period ${closeYear}-${String(closeMonth).padStart(2, '0')} closed successfully.`)
    },
    onError: (err: any) => {
      showMsg(err?.error?.message || 'Failed to close period.')
    },
  })

  const reopenMutation = useMutation({
    mutationFn: (periodId: string) => reopenPeriod(periodId, { notes: reopenNotes || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounting-periods'] })
      setReopenId(null)
      setReopenNotes('')
      showMsg('Period reopened successfully.')
    },
    onError: (err: any) => {
      showMsg(err?.error?.message || 'Failed to reopen period.')
    },
  })

  const periods: AccountingPeriod[] = periodsQuery.data?.data ?? []
  const currentYear = new Date().getFullYear()
  const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Accounting Periods</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Close periods to prevent any expense or invoice changes in that month.
        </p>
      </div>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Close period form */}
      <form
        onSubmit={(e) => { e.preventDefault(); closeMutation.mutate() }}
        className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
      >
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Close a Period</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Year</label>
            <select
              value={closeYear}
              onChange={(e) => setCloseYear(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Month</label>
            <select
              value={closeMonth}
              onChange={(e) => setCloseMonth(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {MONTH_NAMES.map((name, i) => (
                <option key={i + 1} value={i + 1}>{name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes (optional)</label>
            <input
              type="text"
              value={closeNotes}
              onChange={(e) => setCloseNotes(e.target.value)}
              placeholder="Reason for closing..."
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={closeMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
        >
          <Lock className="w-4 h-4" />
          {closeMutation.isPending ? 'Closing...' : 'Close Period'}
        </button>
      </form>

      {/* Periods grid */}
      <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Period History</h3>
        </div>
        {periods.length === 0 ? (
          <div className="text-center py-12">
            <CalendarDays className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 text-sm">No periods have been closed yet.</p>
            <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
              All periods are open by default until explicitly closed.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700">
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Period</th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Closed At</th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Notes</th>
                <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => (
                <tr key={period.id} className="border-b border-gray-50">
                  <td className="px-5 py-3 text-gray-900 dark:text-gray-100 font-medium">
                    {MONTH_NAMES[period.month - 1]} {period.year}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        period.status === 'closed'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {period.status === 'closed' ? 'Closed' : 'Open'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500 dark:text-gray-400">
                    {period.closed_at
                      ? new Date(period.closed_at).toLocaleDateString()
                      : '--'}
                  </td>
                  <td className="px-5 py-3 text-gray-500 dark:text-gray-400 max-w-[200px] truncate">
                    {period.notes || '--'}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {period.status === 'closed' ? (
                      reopenId === period.id ? (
                        <div className="flex items-center gap-2 justify-end">
                          <input
                            type="text"
                            value={reopenNotes}
                            onChange={(e) => setReopenNotes(e.target.value)}
                            placeholder="Reason..."
                            className="px-2 py-1 border rounded text-xs w-32 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                          <button
                            onClick={() => reopenMutation.mutate(period.id)}
                            disabled={reopenMutation.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                          >
                            <Unlock className="w-3 h-3" />
                            Confirm
                          </button>
                          <button
                            onClick={() => { setReopenId(null); setReopenNotes('') }}
                            className="px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-800"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setReopenId(period.id)}
                          className="flex items-center gap-1 px-2 py-1 text-xs text-green-700 border border-green-200 rounded hover:bg-green-50 ml-auto"
                        >
                          <Unlock className="w-3 h-3" />
                          Reopen
                        </button>
                      )
                    ) : (
                      <span className="text-xs text-gray-400 dark:text-gray-500">Open</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How period locking works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Closing a period prevents creating or editing expenses and invoices dated in that period</li>
          <li>Only admins can close or reopen periods</li>
          <li>All periods are open by default until explicitly closed</li>
          <li>Reopening a period allows changes again -- use with caution</li>
        </ul>
      </div>
    </div>
  )
}
