import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { FileCheck2, Loader2, FileDown, CheckCircle2, AlertTriangle, Circle, Info, ChevronRight, ChevronDown } from 'lucide-react'
import { getFilingPackage, downloadFilingPdf, type FilingPackage, type ReadinessItem, type T2125Line } from '@/api/filing'
import { formatDate } from '@/lib/utils'

const money = (n: string | number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(typeof n === 'string' ? parseFloat(n) : n)

export default function FilingPage() {
  const { t } = useTranslation('filing')
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const { data, isLoading } = useQuery({ queryKey: ['filing-package', year], queryFn: () => getFilingPackage(year) })
  const pkg: FilingPackage | undefined = data?.data
  const [busy, setBusy] = useState(false)

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <FileCheck2 className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('title')}</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-2xl">{t('subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">{t('year')}</label>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="px-2 py-1.5 border rounded-md text-sm bg-white dark:bg-gray-900">
            {[thisYear, thisYear - 1, thisYear - 2].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button
            onClick={() => { setBusy(true); downloadFilingPdf(year).catch((e: any) => toast.error(e?.message || 'Download failed')).finally(() => setBusy(false)) }}
            disabled={busy || !pkg}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileDown className="w-4 h-4" />} {t('download')}
          </button>
        </div>
      </div>

      {isLoading || !pkg ? (
        <div className="flex items-center justify-center py-16 text-gray-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <>
          <p className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 rounded-lg px-3 py-2">
            {pkg.personal_included ? t('personalOnlyOwner') : t('accountantView')}
          </p>

          <Readiness items={pkg.readiness} />

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-3"><T2125 pkg={pkg} /></div>
            <div className="lg:col-span-2"><T1 pkg={pkg} /></div>
          </div>
        </>
      )}
    </div>
  )
}

function Readiness({ items }: { items: ReadinessItem[] }) {
  const { t } = useTranslation('filing')
  const icon = { ok: CheckCircle2, warn: AlertTriangle, todo: Circle, info: Info }
  const color = { ok: 'text-green-600', warn: 'text-amber-600', todo: 'text-gray-400', info: 'text-blue-500' }
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-2.5 bg-gray-50 dark:bg-gray-900/50 text-xs font-medium text-gray-600 dark:text-gray-300 uppercase tracking-wide">{t('readiness.title')}</div>
      <ul className="divide-y divide-gray-100 dark:divide-gray-800">
        {items.map((i) => {
          const I = icon[i.status]
          return (
            <li key={i.key} className="flex items-start gap-3 px-4 py-2.5 text-sm">
              <I className={`w-4 h-4 mt-0.5 shrink-0 ${color[i.status]}`} />
              <div className="flex-1 min-w-0">
                <div className="text-gray-900 dark:text-gray-100">{i.label}</div>
                {i.detail && <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{i.detail}</div>}
              </div>
              {i.action_path && i.status !== 'ok' && (
                <Link to={i.action_path} className="text-xs text-blue-600 hover:underline shrink-0">{t('readiness.fix')} →</Link>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function T2125({ pkg }: { pkg: FilingPackage }) {
  const { t } = useTranslation('filing')
  const s = pkg.t2125
  const expenses = s.lines.filter((l) => l.part === '4 expenses')
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('t2125.title')}</h2>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('t2125.subtitle', { start: formatDate(s.period_start), end: formatDate(s.period_end) })}</p>
      </div>
      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden text-sm">
        <Row k={t('t2125.grossSales')} v={money(s.gross_sales)} />
        <Row k={t('t2125.otherIncome')} v={money(s.other_income)} />
        <Row k={t('t2125.grossIncome')} v={money(s.gross_income)} strong />
        <Row k={t('t2125.cogs')} v={`− ${money(s.cost_of_goods_sold)}`} />
        <Row k={t('t2125.grossProfit')} v={money(s.gross_profit)} strong />
      </div>

      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900/50 text-[11px] text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            <tr>
              <th className="text-left px-3 py-2 font-medium w-8" />
              <th className="text-left px-3 py-2 font-medium">{t('t2125.line')}</th>
              <th className="text-left px-3 py-2 font-medium">{t('t2125.expenses')}</th>
              <th className="text-right px-3 py-2 font-medium">{t('t2125.books')}</th>
              <th className="text-right px-3 py-2 font-medium">{t('t2125.allowable')}</th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((l) => <ExpenseRow key={l.line} l={l} />)}
            <tr className="border-t border-gray-200 dark:border-gray-700 font-medium">
              <td /><td className="px-3 py-2 font-mono text-xs">9368</td><td className="px-3 py-2">{t('t2125.totalExpenses').replace(/^9368 /, '')}</td>
              <td /><td className="px-3 py-2 text-right tabular-nums">{money(s.total_expenses)}</td>
            </tr>
            <tr className="bg-gray-50 dark:bg-gray-900/50 font-semibold">
              <td /><td className="px-3 py-2 font-mono text-xs">9369</td><td className="px-3 py-2">{t('t2125.netIncome').replace(/^9369 /, '')}</td>
              <td /><td className="px-3 py-2 text-right tabular-nums text-gray-900 dark:text-gray-100">{money(s.net_income)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {(s.excluded_non_deductible.length > 0 || s.unmapped.length > 0) && (
        <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          {s.excluded_non_deductible.length > 0 && <p><b>{t('t2125.excluded')}:</b> {s.excluded_non_deductible.map((x) => `${x.name} ${money(x.amount)}`).join(' · ')}</p>}
          {s.unmapped.length > 0 && <p><b>{t('t2125.unmapped')}:</b> {s.unmapped.map((x) => `${x.name} ${money(x.amount)}`).join(' · ')}</p>}
        </div>
      )}

      {s.gst_hst?.has_recorded_tax && (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden text-sm">
          <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900/50 text-[11px] uppercase tracking-wide text-gray-500">{t('t2125.gst')}</div>
          <Row k="101 Sales" v={money(s.gst_hst.line_101_sales)} />
          <Row k="105 GST/HST collected" v={money(s.gst_hst.line_105_collected)} />
          <Row k="108 Input tax credits" v={money(s.gst_hst.line_108_itc)} />
          <Row k="109 Net tax" v={money(s.gst_hst.line_109_net_tax)} strong />
        </div>
      )}
    </div>
  )
}

function ExpenseRow({ l }: { l: T2125Line }) {
  const { t } = useTranslation('filing')
  const [open, setOpen] = useState(false)
  const has = l.sources.length > 0
  return (
    <>
      <tr className={`border-t border-gray-100 dark:border-gray-800 ${has ? 'cursor-pointer hover:bg-gray-50/60 dark:hover:bg-gray-900/40' : ''}`} onClick={() => has && setOpen((v) => !v)}>
        <td className="px-3 py-2 text-gray-400">{has ? (open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />) : null}</td>
        <td className="px-3 py-2 font-mono text-xs text-gray-500">{l.line}</td>
        <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{l.label}{l.computed && <span className="ml-2 text-[11px] italic text-amber-600">{t('t2125.computed')}</span>}</td>
        <td className="px-3 py-2 text-right tabular-nums text-gray-500">{l.computed ? '—' : money(l.amount)}</td>
        <td className="px-3 py-2 text-right tabular-nums">{l.computed ? '—' : money(l.allowable)}</td>
      </tr>
      {open && l.sources.map((src, i) => (
        <tr key={i} className="bg-gray-50/50 dark:bg-gray-900/30 text-xs text-gray-600 dark:text-gray-400">
          <td /><td className="px-3 py-1 font-mono">{src.code}</td><td className="px-3 py-1">{src.name}</td>
          <td className="px-3 py-1 text-right tabular-nums">{money(src.amount)}</td><td />
        </tr>
      ))}
    </>
  )
}

function T1({ pkg }: { pkg: FilingPackage }) {
  const { t } = useTranslation('filing')
  const p = pkg.t1
  if (!p) return null
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('t1.title')}</h2>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{t('t1.subtitle')}</p>
      </div>
      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden text-sm">
        <Row k={t('t1.netBusiness')} v={money(p.net_business_income_line_13500)} strong />
        {p.lines.map((l) => <Row key={l.line} k={`${l.line} ${l.label}`} sub={`${l.transaction_count} txn`} v={money(l.amount)} />)}
        {p.lines.length === 0 && (
          <div className="px-3 py-3 text-xs text-gray-500 dark:text-gray-400">
            <p>{t('t1.noLines')}</p>
            <p className="mt-1">{t('t1.hint')}</p>
          </div>
        )}
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{t('t1.totals', { in: money(p.total_in), out: money(p.total_out), unc: money(p.uncategorized_out) })}</p>
    </div>
  )
}

function Row({ k, v, sub, strong }: { k: string; v: string; sub?: string; strong?: boolean }) {
  return (
    <div className={`flex items-center justify-between gap-3 px-3 py-2 border-t first:border-t-0 border-gray-100 dark:border-gray-800 ${strong ? 'bg-gray-50/70 dark:bg-gray-900/40 font-medium' : ''}`}>
      <div className="min-w-0">
        <div className="text-gray-800 dark:text-gray-200 truncate">{k}</div>
        {sub && <div className="text-[11px] text-gray-500">{sub}</div>}
      </div>
      <div className="tabular-nums text-gray-900 dark:text-gray-100 shrink-0">{v}</div>
    </div>
  )
}
