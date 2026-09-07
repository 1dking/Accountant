import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Plus, Wallet, Loader2, Users, X, Calculator, Landmark } from 'lucide-react'
import {
  listRuns, createRun, listEmployees, getRemittance,
  type RunSummary, type RunStatus, type PayFrequency, type Employee, type StubOverride,
} from '@/api/payroll'
import { formatDate } from '@/lib/utils'

const money = (n: string | number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(typeof n === 'string' ? parseFloat(n) : n)

const STATUS_STYLE: Record<RunStatus, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300',
  approved: 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300',
  paid: 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300',
  void: 'bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400',
}

export default function PayrollRunsPage() {
  const { t } = useTranslation('payroll')
  const [creating, setCreating] = useState(false)
  const { data, isLoading } = useQuery({ queryKey: ['payroll-runs'], queryFn: () => listRuns() })
  const runs: RunSummary[] = data?.data ?? []

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Wallet className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('title')}</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-2xl">{t('subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/payroll/employees" className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            <Users className="w-4 h-4" /> {t('tabs.employees')}
          </Link>
          <button onClick={() => setCreating(true)} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Plus className="w-4 h-4" /> {t('runs.new')}
          </button>
        </div>
      </div>

      <RemittanceCard />

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : runs.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <Wallet className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">{t('runs.empty')}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('runs.emptyHint')}</p>
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-500 dark:text-gray-400">
              <tr>
                <th className="text-left px-4 py-2 font-medium">{t('runs.period')}</th>
                <th className="text-left px-4 py-2 font-medium">{t('runs.payDate')}</th>
                <th className="text-left px-4 py-2 font-medium">{t('runs.frequency')}</th>
                <th className="text-right px-4 py-2 font-medium">{t('runs.gross')}</th>
                <th className="text-right px-4 py-2 font-medium">{t('runs.net')}</th>
                <th className="text-right px-4 py-2 font-medium">{t('runs.remittance')}</th>
                <th className="text-left px-4 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50/60 dark:hover:bg-gray-900/40">
                  <td className="px-4 py-3">
                    <Link to={`/payroll/runs/${r.id}`} className="font-medium text-gray-900 dark:text-gray-100 hover:underline">
                      {formatDate(r.period_start)} – {formatDate(r.period_end)}
                    </Link>
                    <div className="text-xs text-gray-500">{t('runs.employees', { count: r.stub_count })}</div>
                  </td>
                  <td className="px-4 py-3">{formatDate(r.pay_date)}</td>
                  <td className="px-4 py-3 text-xs">{t(`employees.fields.${r.pay_frequency}`)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{money(r.total_gross)}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">{money(r.total_net)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{money(r.total_remittance)}</td>
                  <td className="px-4 py-3"><span className={`text-[11px] px-1.5 py-0.5 rounded ${STATUS_STYLE[r.status]}`}>{t(`runs.status.${r.status}`)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && <NewRunModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function RemittanceCard() {
  const { t } = useTranslation('payroll')
  const now = new Date()
  const [ym, setYm] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  const [y, m] = ym.split('-').map(Number)
  const { data } = useQuery({ queryKey: ['payroll-remittance', y, m], queryFn: () => getRemittance(y, m) })
  const r = data?.data
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-xl p-4 sm:p-5 bg-gray-50/50 dark:bg-gray-900/30">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <Landmark className="w-4 h-4 text-gray-500" />
          <h2 className="font-medium text-gray-900 dark:text-gray-100">{t('remittance.title')}</h2>
        </div>
        <input type="month" value={ym} onChange={(e) => setYm(e.target.value)} className="px-2 py-1 border rounded-md text-sm bg-white dark:bg-gray-900" />
      </div>
      {r && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
          <Stat label={t('remittance.gross')} value={money(r.gross_payroll)} sub={`${r.run_count} ${t('remittance.runs').toLowerCase()} · ${r.employee_count} ${t('remittance.employees').toLowerCase()}`} />
          <Stat label={`${t('remittance.cppEmployee')} + ${t('remittance.cppEmployer').split('—')[1]?.trim() ?? ''}`} value={money(parseFloat(r.cpp_employee) + parseFloat(r.cpp_employer))} />
          <Stat label={`${t('remittance.eiEmployee')} + ${t('remittance.eiEmployer').split('—')[1]?.trim() ?? ''}`} value={money(parseFloat(r.ei_employee) + parseFloat(r.ei_employer))} />
          <Stat label={t('remittance.tax')} value={money(r.income_tax)} />
          <Stat label={t('remittance.total')} value={money(r.total_cra)} sub={`${t('remittance.due')} ${formatDate(r.due_date)}`} strong />
          {parseFloat(r.total_revenu_quebec) > 0 && <Stat label={t('remittance.quebec')} value={money(r.total_revenu_quebec)} />}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, sub, strong }: { label: string; value: string; sub?: string; strong?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`tabular-nums ${strong ? 'text-lg font-semibold text-gray-900 dark:text-gray-100' : 'text-gray-800 dark:text-gray-200'}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-500">{sub}</div>}
    </div>
  )
}

function NewRunModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('payroll')
  const { t: tc } = useTranslation('common')
  const navigate = useNavigate()
  const today = new Date()
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  const twoWeeksAgo = new Date(today); twoWeeksAgo.setDate(today.getDate() - 13)
  const [freq, setFreq] = useState<PayFrequency>('biweekly')
  const [start, setStart] = useState(iso(twoWeeksAgo))
  const [end, setEnd] = useState(iso(today))
  const [payDate, setPayDate] = useState(iso(today))
  const [ov, setOv] = useState<Record<string, StubOverride>>({})

  const { data } = useQuery({ queryKey: ['payroll-employees', false], queryFn: () => listEmployees(false) })
  const employees: Employee[] = (data?.data ?? []).filter((e) => e.status === 'active' && e.pay_frequency === freq)

  const create = useMutation({
    mutationFn: () => createRun({ period_start: start, period_end: end, pay_date: payDate, pay_frequency: freq, overrides: Object.values(ov) }),
    onSuccess: (res) => { toast.success(t('runs.created')); onClose(); navigate(`/payroll/runs/${res.data.id}`) },
    onError: (err: any) => toast.error(err?.message || t('runs.createFailed')),
  })

  const setO = (id: string, k: keyof StubOverride, v: any) => setOv((o) => ({ ...o, [id]: { ...(o[id] ?? { employee_id: id }), [k]: v } }))
  const inp = 'w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const lab = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); create.mutate() }}
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-2xl p-6 space-y-5 my-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('runs.new')}</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <label className={lab}>{t('runs.frequency')}</label>
            <select className={inp} value={freq} onChange={(e) => setFreq(e.target.value as PayFrequency)}>
              {(['weekly', 'biweekly', 'semimonthly', 'monthly'] as PayFrequency[]).map((f) => <option key={f} value={f}>{t(`employees.fields.${f}`)}</option>)}
            </select>
          </div>
          <div><label className={lab}>{t('runs.period')} —</label><input type="date" required className={inp} value={start} onChange={(e) => setStart(e.target.value)} /></div>
          <div><label className={lab}>&nbsp;</label><input type="date" required className={inp} value={end} onChange={(e) => setEnd(e.target.value)} /></div>
          <div><label className={lab}>{t('runs.payDate')}</label><input type="date" required className={inp} value={payDate} onChange={(e) => setPayDate(e.target.value)} /></div>
        </div>

        <div>
          <p className="text-xs text-gray-500 mb-2">{t('runs.overridesHint')}</p>
          <div className="border border-gray-200 dark:border-gray-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/50 text-[11px] text-gray-500">
                <tr>
                  <th className="text-left px-3 py-1.5 font-medium">{t('tabs.employees')}</th>
                  <th className="text-left px-3 py-1.5 font-medium">{t('run.stub.hours')}</th>
                  <th className="text-left px-3 py-1.5 font-medium">{t('run.stub.overtime')}</th>
                  <th className="text-left px-3 py-1.5 font-medium">{t('run.stub.bonus')}</th>
                </tr>
              </thead>
              <tbody>
                {employees.length === 0 ? (
                  <tr><td colSpan={4} className="px-3 py-4 text-center text-gray-500 text-xs">{t('employees.empty')}</td></tr>
                ) : employees.map((e) => (
                  <tr key={e.id} className="border-t border-gray-100 dark:border-gray-800">
                    <td className="px-3 py-1.5">{e.full_name} <span className="text-xs text-gray-400 font-mono">{e.province_of_employment}</span></td>
                    <td className="px-3 py-1.5"><input type="number" step="0.25" min="0" disabled={e.pay_type !== 'hourly'} placeholder={e.default_hours_per_period ?? '—'} className="w-20 px-2 py-1 border rounded text-sm bg-white dark:bg-gray-900 tabular-nums disabled:opacity-40" onChange={(ev) => setO(e.id, 'hours', ev.target.value === '' ? null : parseFloat(ev.target.value))} /></td>
                    <td className="px-3 py-1.5"><input type="number" step="0.01" min="0" placeholder="0" className="w-24 px-2 py-1 border rounded text-sm bg-white dark:bg-gray-900 tabular-nums" onChange={(ev) => setO(e.id, 'overtime_pay', parseFloat(ev.target.value) || 0)} /></td>
                    <td className="px-3 py-1.5"><input type="number" step="0.01" min="0" placeholder="0" className="w-24 px-2 py-1 border rounded text-sm bg-white dark:bg-gray-900 tabular-nums" onChange={(ev) => setO(e.id, 'bonus', parseFloat(ev.target.value) || 0)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">{tc('actions.cancel')}</button>
          <button type="submit" disabled={create.isPending || employees.length === 0} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Calculator className="w-4 h-4" /> {create.isPending ? tc('actions.saving') : t('runs.create')}
          </button>
        </div>
      </form>
    </div>
  )
}
