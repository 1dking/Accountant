import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Scale, Loader2, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  getTrialBalance,
  getGeneralLedger,
  type GeneralLedgerAccount,
} from '@/api/accounting'
import { formatDate } from '@/lib/utils'

type Tab = 'trial-balance' | 'general-ledger'

function money(n: string): string {
  const v = parseFloat(n)
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function LedgerReportsPage() {
  const [tab, setTab] = useState<Tab>('trial-balance')
  const today = new Date().toISOString().slice(0, 10)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState(today)

  const params = { date_from: dateFrom || undefined, date_to: dateTo || undefined }

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <Scale className="w-6 h-6 text-gray-700 dark:text-gray-300" />
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Ledger Reports</h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Double-entry reports computed live over both your journal entries and cashbook activity.
        </p>
      </div>

      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {(['trial-balance', 'general-ledger'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-sm rounded-md ${
                tab === t
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400'
              }`}
            >
              {t === 'trial-balance' ? 'Trial Balance' : 'General Ledger'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-2 py-1.5 border rounded-lg dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            title="From (optional)"
          />
          <span className="text-gray-400">→</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-2 py-1.5 border rounded-lg dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            title="As of"
          />
        </div>
      </div>

      {tab === 'trial-balance' ? <TrialBalanceView params={params} /> : <GeneralLedgerView params={params} />}
    </div>
  )
}

function TrialBalanceView({ params }: { params: { date_from?: string; date_to?: string } }) {
  const { data, isLoading } = useQuery({
    queryKey: ['trial-balance', params],
    queryFn: () => getTrialBalance(params),
  })
  const tb = data?.data

  if (isLoading) return <Spinner />
  if (!tb) return null

  return (
    <div className="space-y-3">
      <div
        className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
          tb.balanced
            ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300'
            : 'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300'
        }`}
      >
        {tb.balanced ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
        {tb.balanced ? 'In balance — debits equal credits.' : 'Out of balance — this should never happen; please report it.'}
      </div>

      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 dark:text-gray-400">
            <tr>
              <th className="text-left font-medium px-4 py-2">Account</th>
              <th className="text-right font-medium px-4 py-2 w-32">Debit</th>
              <th className="text-right font-medium px-4 py-2 w-32">Credit</th>
            </tr>
          </thead>
          <tbody>
            {tb.rows.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                  No postings in this period yet.
                </td>
              </tr>
            ) : (
              tb.rows.map((r) => (
                <tr key={r.code} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-4 py-2 text-gray-900 dark:text-gray-100">
                    <span className="font-mono text-gray-400 mr-2">{r.code}</span>
                    {r.name}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {parseFloat(r.debit) > 0 ? money(r.debit) : ''}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {parseFloat(r.credit) > 0 ? money(r.credit) : ''}
                  </td>
                </tr>
              ))
            )}
          </tbody>
          <tfoot className="border-t-2 border-gray-200 dark:border-gray-700 font-semibold">
            <tr>
              <td className="px-4 py-2 text-right text-gray-500 dark:text-gray-400">Totals</td>
              <td className="px-4 py-2 text-right tabular-nums">{money(tb.total_debit)}</td>
              <td className="px-4 py-2 text-right tabular-nums">{money(tb.total_credit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

function GeneralLedgerView({ params }: { params: { date_from?: string; date_to?: string } }) {
  const { data, isLoading } = useQuery({
    queryKey: ['general-ledger', params],
    queryFn: () => getGeneralLedger(params),
  })
  const accounts = data?.data?.accounts ?? []

  if (isLoading) return <Spinner />

  if (accounts.length === 0) {
    return (
      <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl text-gray-400">
        No postings in this period yet.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {accounts.map((a) => (
        <GLAccountRow key={a.code} account={a} />
      ))}
    </div>
  )
}

function GLAccountRow({ account }: { account: GeneralLedgerAccount }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
      >
        {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        <span className="font-mono text-xs text-gray-400 w-12">{account.code}</span>
        <span className="text-sm text-gray-900 dark:text-gray-100 flex-1 truncate">{account.name}</span>
        <span className="text-xs text-gray-400">{account.postings.length} postings</span>
        <span className="text-sm font-medium tabular-nums">${money(account.closing_balance)}</span>
      </button>
      {open && (
        <div className="border-t border-gray-100 dark:border-gray-800 overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead className="bg-gray-50 dark:bg-gray-800/40 text-xs text-gray-400">
              <tr>
                <th className="text-left font-medium px-4 py-1.5 w-24">Date</th>
                <th className="text-left font-medium px-2 py-1.5 w-20">Ref</th>
                <th className="text-left font-medium px-2 py-1.5">Memo</th>
                <th className="text-right font-medium px-2 py-1.5 w-24">Debit</th>
                <th className="text-right font-medium px-2 py-1.5 w-24">Credit</th>
                <th className="text-right font-medium px-4 py-1.5 w-28">Balance</th>
              </tr>
            </thead>
            <tbody>
              {account.postings.map((p, i) => (
                <tr key={i} className="border-t border-gray-50 dark:border-gray-800/50 text-gray-700 dark:text-gray-300">
                  <td className="px-4 py-1.5 whitespace-nowrap">{formatDate(p.date)}</td>
                  <td className="px-2 py-1.5 font-mono text-xs text-gray-400">{p.ref}</td>
                  <td className="px-2 py-1.5 truncate max-w-[180px]">{p.memo}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{parseFloat(p.debit) > 0 ? money(p.debit) : ''}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{parseFloat(p.credit) > 0 ? money(p.credit) : ''}</td>
                  <td className="px-4 py-1.5 text-right tabular-nums">{money(p.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16 text-gray-400">
      <Loader2 className="w-6 h-6 animate-spin" />
    </div>
  )
}
