import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, BookText, Loader2, Check, X, Trash2, Ban } from 'lucide-react'
import {
  listJournalEntries,
  createJournalEntry,
  voidJournalEntry,
  listChartAccounts,
  type JournalEntry,
  type JournalLineInput,
  type ChartAccount,
} from '@/api/accounting'
import { formatDate } from '@/lib/utils'

function money(n: string | number): string {
  const v = typeof n === 'string' ? parseFloat(n) : n
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function JournalPage() {
  const [creating, setCreating] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['journal-entries'],
    queryFn: () => listJournalEntries({}),
  })
  const entries: JournalEntry[] = data?.data ?? []

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <BookText className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Journal Entries</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manual double-entry adjustments. Every entry must balance — total debits equal total credits —
            and posts to your Chart of Accounts.
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New entry
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <BookText className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">No journal entries yet</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Post a manual adjusting entry — a depreciation charge, an accrual, an opening balance.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <JournalRow key={e.id} entry={e} />
          ))}
        </div>
      )}

      {creating && <NewEntryModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function JournalRow({ entry }: { entry: JournalEntry }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const voidMutation = useMutation({
    mutationFn: () => voidJournalEntry(entry.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['journal-entries'] })
      toast.success('Entry voided')
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to void entry'),
  })

  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
      >
        <span className="font-mono text-xs text-gray-400 w-10 shrink-0">#{entry.entry_number}</span>
        <span className="text-sm text-gray-500 dark:text-gray-400 w-24 shrink-0">{formatDate(entry.date)}</span>
        <span className="text-sm text-gray-900 dark:text-gray-100 flex-1 truncate">
          {entry.memo || <span className="text-gray-400">No memo</span>}
        </span>
        {entry.status === 'void' && (
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400">
            void
          </span>
        )}
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100 tabular-nums">${money(entry.total)}</span>
      </button>
      {expanded && (
        <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 text-left">
                <th className="font-medium pb-1">Account</th>
                <th className="font-medium pb-1 text-right">Debit</th>
                <th className="font-medium pb-1 text-right">Credit</th>
              </tr>
            </thead>
            <tbody>
              {entry.lines.map((ln) => (
                <tr key={ln.id} className="text-gray-700 dark:text-gray-300">
                  <td className="py-0.5">
                    <span className="font-mono text-gray-400 mr-2">{ln.account_code}</span>
                    {ln.account_name}
                    {ln.description && <span className="text-gray-400"> — {ln.description}</span>}
                  </td>
                  <td className="py-0.5 text-right tabular-nums">
                    {parseFloat(ln.debit) > 0 ? money(ln.debit) : ''}
                  </td>
                  <td className="py-0.5 text-right tabular-nums">
                    {parseFloat(ln.credit) > 0 ? money(ln.credit) : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {entry.status === 'posted' && (
            <div className="flex justify-end mt-2">
              <button
                onClick={() => voidMutation.mutate()}
                disabled={voidMutation.isPending}
                className="flex items-center gap-1 text-xs text-red-600 hover:bg-red-50 dark:hover:bg-red-950 px-2 py-1 rounded disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5" /> Void entry
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

type DraftLine = { account_id: string; debit: string; credit: string; description: string }

const emptyLine = (): DraftLine => ({ account_id: '', debit: '', credit: '', description: '' })

function NewEntryModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10))
  const [memo, setMemo] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()])

  const { data: accountsData } = useQuery({
    queryKey: ['coa-accounts', false],
    queryFn: () => listChartAccounts({}),
  })
  const accounts: ChartAccount[] = accountsData?.data ?? []

  const totals = useMemo(() => {
    const debit = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0)
    const credit = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0)
    return { debit, credit, balanced: debit === credit && debit > 0 }
  }, [lines])

  const setLine = (i: number, patch: Partial<DraftLine>) =>
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))

  const mutation = useMutation({
    mutationFn: () => {
      const payloadLines: JournalLineInput[] = lines
        .filter((l) => l.account_id && (parseFloat(l.debit) > 0 || parseFloat(l.credit) > 0))
        .map((l) => ({
          account_id: l.account_id,
          debit: (parseFloat(l.debit) || 0).toFixed(2),
          credit: (parseFloat(l.credit) || 0).toFixed(2),
          description: l.description || null,
        }))
      return createJournalEntry({ date: entryDate, memo: memo || null, lines: payloadLines })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['journal-entries'] })
      toast.success('Journal entry posted')
      onClose()
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to post entry'),
  })

  const canSubmit = totals.balanced && lines.filter((l) => l.account_id).length >= 2

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">New Journal Entry</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date</label>
              <input
                type="date"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Memo</label>
              <input
                type="text"
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="e.g. Monthly depreciation"
                className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center text-xs text-gray-400 px-1">
              <span className="flex-1">Account</span>
              <span className="w-24 text-right">Debit</span>
              <span className="w-24 text-right">Credit</span>
              <span className="w-8" />
            </div>
            {lines.map((line, i) => (
              <div key={i} className="flex items-center gap-2">
                <select
                  value={line.account_id}
                  onChange={(e) => setLine(i, { account_id: e.target.value })}
                  className="flex-1 px-2 py-1.5 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                >
                  <option value="">Select account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={line.debit}
                  onChange={(e) => setLine(i, { debit: e.target.value, credit: e.target.value ? '' : line.credit })}
                  className="w-24 px-2 py-1.5 border rounded-lg text-sm text-right dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={line.credit}
                  onChange={(e) => setLine(i, { credit: e.target.value, debit: e.target.value ? '' : line.debit })}
                  className="w-24 px-2 py-1.5 border rounded-lg text-sm text-right dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
                <button
                  onClick={() => setLines((prev) => (prev.length > 2 ? prev.filter((_, idx) => idx !== i) : prev))}
                  disabled={lines.length <= 2}
                  className="p-1.5 text-gray-400 hover:text-red-600 disabled:opacity-30 rounded"
                  title="Remove line"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button
              onClick={() => setLines((prev) => [...prev, emptyLine()])}
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 px-1 pt-1"
            >
              <Plus className="w-4 h-4" /> Add line
            </button>
          </div>

          <div className="flex items-center justify-end gap-6 text-sm border-t dark:border-gray-700 pt-3">
            <div className="text-right">
              <div className="text-xs text-gray-400">Debits</div>
              <div className="tabular-nums font-medium">${money(totals.debit)}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-400">Credits</div>
              <div className="tabular-nums font-medium">${money(totals.credit)}</div>
            </div>
            <div
              className={`text-xs px-2 py-1 rounded ${
                totals.balanced
                  ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300'
                  : 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
              }`}
            >
              {totals.balanced ? 'Balanced' : `Out by $${money(Math.abs(totals.debit - totals.credit))}`}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t dark:border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !canSubmit}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            title={canSubmit ? '' : 'Entry must balance and use at least two accounts'}
          >
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            Post entry
          </button>
        </div>
      </div>
    </div>
  )
}
