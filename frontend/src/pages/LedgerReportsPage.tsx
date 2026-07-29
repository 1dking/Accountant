import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Scale, Loader2, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, Download, TrendingUp } from 'lucide-react'
import {
  getTrialBalance,
  getGeneralLedger,
  getProfitLoss,
  getBalanceSheet,
  getMarketingPerformance,
  getGstHstReturn,
  downloadStatementPdf,
  type GeneralLedgerAccount,
  type StatementLine,
} from '@/api/accounting'
import { formatDate } from '@/lib/utils'

type Tab = 'profit-loss' | 'balance-sheet' | 'marketing' | 'gst-hst' | 'trial-balance' | 'general-ledger'
const TAB_LABELS: Record<Tab, string> = {
  'profit-loss': 'Profit & Loss',
  'balance-sheet': 'Balance Sheet',
  'marketing': 'Marketing ROAS',
  'gst-hst': 'GST/HST',
  'trial-balance': 'Trial Balance',
  'general-ledger': 'General Ledger',
}

function money(n: string): string {
  const v = parseFloat(n)
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function LedgerReportsPage() {
  const [tab, setTab] = useState<Tab>('profit-loss')
  const today = new Date().toISOString().slice(0, 10)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState(today)

  const params = { date_from: dateFrom || undefined, date_to: dateTo || undefined }
  const [downloading, setDownloading] = useState(false)
  const exportable = tab === 'profit-loss' || tab === 'balance-sheet'

  async function handleExport() {
    setDownloading(true)
    try {
      if (tab === 'balance-sheet') {
        await downloadStatementPdf('balance-sheet', { as_of: dateTo || undefined })
      } else {
        await downloadStatementPdf('profit-loss', params)
      }
    } catch {
      alert('Could not generate the PDF. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <Scale className="w-6 h-6 text-gray-700 dark:text-gray-300" />
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Financial Statements</h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Profit &amp; Loss, Balance Sheet, Trial Balance and General Ledger — computed live from your
          cashbook and journal, so they always tie out.
        </p>
      </div>

      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {(['profit-loss', 'balance-sheet', 'marketing', 'gst-hst', 'trial-balance', 'general-ledger'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-sm rounded-md ${
                tab === t
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400'
              }`}
            >
              {TAB_LABELS[t]}
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
          {exportable && (
            <button
              onClick={handleExport}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 text-sm font-medium disabled:opacity-60 hover:opacity-90"
              title={`Download the ${tab === 'balance-sheet' ? 'Balance Sheet' : 'P&L'} as a PDF`}
            >
              {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              PDF
            </button>
          )}
        </div>
      </div>

      {tab === 'profit-loss' && <ProfitLossView params={params} />}
      {tab === 'balance-sheet' && <BalanceSheetView asOf={dateTo || undefined} />}
      {tab === 'marketing' && <MarketingView params={params} />}
      {tab === 'gst-hst' && <GstHstView params={params} />}
      {tab === 'trial-balance' && <TrialBalanceView params={params} />}
      {tab === 'general-ledger' && <GeneralLedgerView params={params} />}
    </div>
  )
}

function StatementSection({ title, lines, total }: { title: string; lines: StatementLine[]; total: string }) {
  return (
    <div>
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{title}</div>
      {lines.length === 0 ? (
        <div className="px-4 py-3 text-sm text-gray-400">None</div>
      ) : lines.map((l) => (
        <div key={l.code} className="flex justify-between gap-3 px-4 py-2 border-t border-gray-100 dark:border-gray-800 text-sm">
          <span className="text-gray-900 dark:text-gray-100 truncate"><span className="font-mono text-gray-400 mr-2">{l.code}</span>{l.name}</span>
          <span className="tabular-nums">${money(l.amount)}</span>
        </div>
      ))}
      <div className="flex justify-between px-4 py-2 border-t border-gray-200 dark:border-gray-700 text-sm font-medium">
        <span className="text-gray-500 dark:text-gray-400">Total {title}</span>
        <span className="tabular-nums">${money(total)}</span>
      </div>
    </div>
  )
}

function ProfitLossView({ params }: { params: { date_from?: string; date_to?: string } }) {
  const { data, isLoading } = useQuery({ queryKey: ['profit-loss', params], queryFn: () => getProfitLoss(params) })
  const pl = data?.data
  if (isLoading) return <Spinner />
  if (!pl) return null
  const net = parseFloat(pl.net_profit)
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <StatementSection title="Revenue" lines={pl.income} total={pl.total_income} />
      <StatementSection title="Expenses" lines={pl.expenses} total={pl.total_expenses} />
      <div className="flex justify-between px-4 py-3 border-t-2 border-gray-200 dark:border-gray-700 font-semibold">
        <span>Net {net >= 0 ? 'profit' : 'loss'}</span>
        <span className={`tabular-nums ${net >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>${money(pl.net_profit)}</span>
      </div>
    </div>
  )
}

function BalanceSheetView({ asOf }: { asOf?: string }) {
  const { data, isLoading } = useQuery({ queryKey: ['balance-sheet', asOf], queryFn: () => getBalanceSheet(asOf) })
  const bs = data?.data
  if (isLoading) return <Spinner />
  if (!bs) return null
  return (
    <div className="space-y-3">
      <div
        className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
          bs.balanced
            ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300'
            : 'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300'
        }`}
      >
        {bs.balanced ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
        {bs.balanced
          ? `Balanced — assets equal liabilities plus equity (as of ${formatDate(bs.as_of)}).`
          : 'Out of balance — this should never happen; please report it.'}
      </div>
      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        <StatementSection title="Assets" lines={bs.assets} total={bs.total_assets} />
        <StatementSection title="Liabilities" lines={bs.liabilities} total={bs.total_liabilities} />
        <StatementSection title="Equity" lines={bs.equity} total={bs.total_equity} />
        <div className="flex justify-between px-4 py-3 border-t-2 border-gray-200 dark:border-gray-700 font-semibold">
          <span>Liabilities + Equity</span>
          <span className="tabular-nums">${money(bs.total_liabilities_equity)}</span>
        </div>
      </div>
    </div>
  )
}

function MarketingView({ params }: { params: { date_from?: string; date_to?: string } }) {
  const { data, isLoading } = useQuery({ queryKey: ['marketing-performance', params], queryFn: () => getMarketingPerformance(params) })
  const mp = data?.data
  if (isLoading) return <Spinner />
  if (!mp) return null
  const hasSpend = mp.blended_roas !== null

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Kpi label="Blended ROAS" value={hasSpend ? `${money(mp.blended_roas as string)}×` : '—'} accent />
        <Kpi label="Revenue" value={`$${money(mp.total_revenue)}`} />
        <Kpi label="Ad spend" value={`$${money(mp.total_ad_spend)}`} />
        <Kpi label="Net of ad spend" value={`$${money(mp.net_after_ad_spend)}`} />
      </div>

      <div className="flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400 px-1">
        <TrendingUp className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          <strong>Blended</strong> — total revenue for every dollar of advertising, across the whole
          business. It measures efficiency, not per-campaign attribution (the cashbook has no click or
          conversion data). Ad spend is any expense categorized as Advertising or Marketing.
        </span>
      </div>

      {!hasSpend ? (
        <div className="px-4 py-8 text-center text-sm text-gray-400 border border-dashed border-gray-200 dark:border-gray-800 rounded-xl">
          No advertising spend in this period. Categorize ad expenses as “Advertising” to see ROAS.
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50">
                <th className="text-left px-4 py-2 font-semibold">Month</th>
                <th className="text-right px-4 py-2 font-semibold">Revenue</th>
                <th className="text-right px-4 py-2 font-semibold">Ad spend</th>
                <th className="text-right px-4 py-2 font-semibold">ROAS</th>
                <th className="text-right px-4 py-2 font-semibold">Net</th>
              </tr>
            </thead>
            <tbody>
              {mp.months.map((m) => (
                <tr key={m.month} className="border-t border-gray-100 dark:border-gray-800">
                  <td className="px-4 py-2 font-mono text-gray-700 dark:text-gray-300">{m.month}</td>
                  <td className="px-4 py-2 text-right tabular-nums">${money(m.revenue)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">${money(m.ad_spend)}</td>
                  <td className="px-4 py-2 text-right tabular-nums font-medium">
                    {m.roas !== null ? `${money(m.roas)}×` : '—'}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">${money(m.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {mp.ad_spend_by_account.length > 0 && (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Ad spend by category
          </div>
          {mp.ad_spend_by_account.map((l) => (
            <div key={l.code} className="flex justify-between gap-3 px-4 py-2 border-t border-gray-100 dark:border-gray-800 text-sm">
              <span className="text-gray-900 dark:text-gray-100 truncate"><span className="font-mono text-gray-400 mr-2">{l.code}</span>{l.name}</span>
              <span className="tabular-nums">${money(l.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 ${accent ? 'border-gray-900 dark:border-gray-100' : 'border-gray-200 dark:border-gray-800'}`}>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${accent ? 'text-gray-900 dark:text-gray-100' : 'text-gray-800 dark:text-gray-200'}`}>{value}</div>
    </div>
  )
}

function GstHstView({ params }: { params: { date_from?: string; date_to?: string } }) {
  const { data, isLoading } = useQuery({ queryKey: ['gst-hst', params], queryFn: () => getGstHstReturn(params) })
  const r = data?.data
  if (isLoading) return <Spinner />
  if (!r) return null
  const net = parseFloat(r.line_109_net_tax)

  const LINE = (num: string, label: string, amount: string, opts?: { strong?: boolean }) => (
    <div className={`flex justify-between gap-3 px-4 py-2.5 border-t border-gray-100 dark:border-gray-800 text-sm ${opts?.strong ? 'font-semibold' : ''}`}>
      <span className="text-gray-900 dark:text-gray-100">
        <span className="font-mono text-gray-400 mr-2">{num}</span>{label}
      </span>
      <span className="tabular-nums">${money(amount)}</span>
    </div>
  )

  return (
    <div className="space-y-3">
      {!r.has_recorded_tax && (
        <div className="flex items-start gap-2 text-sm px-3 py-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-200">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            No GST/HST has been recorded on your cashbook entries yet, so every line is zero. Record the
            tax portion on income and expense entries (or set a default tax rate in Settings → Tax) and
            this return fills in automatically.
          </span>
        </div>
      )}

      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        {LINE('101', 'Sales & other revenue (net of tax)', r.line_101_sales)}
        {LINE('105', 'GST/HST collected on sales', r.line_105_collected)}
        {LINE('108', 'Input tax credits (GST/HST paid on purchases)', r.line_108_itc)}
        <div className={`flex justify-between px-4 py-3 border-t-2 border-gray-200 dark:border-gray-700 font-semibold ${
          net > 0 ? 'text-red-600 dark:text-red-400' : net < 0 ? 'text-green-600 dark:text-green-400' : ''
        }`}>
          <span><span className="font-mono text-gray-400 mr-2">109</span>Net tax {net > 0 ? '(owe CRA)' : net < 0 ? '(refund)' : ''}</span>
          <span className="tabular-nums">${money(r.line_109_net_tax)}</span>
        </div>
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 px-1">
        A summary of recorded GST/HST to hand your accountant — computed from the cashbook for the
        selected period. It is not a filing, and reflects only tax you've recorded on entries.
      </p>
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
