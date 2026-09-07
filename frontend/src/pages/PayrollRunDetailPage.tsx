import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ArrowLeft, Loader2, CheckCircle2, Banknote, Ban, ChevronDown, ChevronRight, BookText } from 'lucide-react'
import { getRun, approveRun, markRunPaid, voidRun, type PayrollRun, type PayStub, type RunStatus } from '@/api/payroll'
import { formatDate } from '@/lib/utils'

const money = (n: string | number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(typeof n === 'string' ? parseFloat(n) : n)
const f = (s: string) => parseFloat(s)

const STATUS_STYLE: Record<RunStatus, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300',
  approved: 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300',
  paid: 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300',
  void: 'bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400',
}

export default function PayrollRunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation('payroll')
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['payroll-run', id], queryFn: () => getRun(id!), enabled: !!id })
  const run: PayrollRun | undefined = data?.data

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['payroll-run', id] })
    qc.invalidateQueries({ queryKey: ['payroll-runs'] })
    qc.invalidateQueries({ queryKey: ['payroll-remittance'] })
    qc.invalidateQueries({ queryKey: ['payroll-employees'] })
    qc.invalidateQueries({ queryKey: ['trial-balance'] })
    qc.invalidateQueries({ queryKey: ['general-ledger'] })
  }
  const approve = useMutation({ mutationFn: () => approveRun(id!), onSuccess: () => { invalidate(); toast.success(t('run.approved')) }, onError: (e: any) => toast.error(e?.message || 'Failed') })
  const paid = useMutation({ mutationFn: () => markRunPaid(id!), onSuccess: () => { invalidate(); toast.success(t('run.paid')) }, onError: (e: any) => toast.error(e?.message || 'Failed') })
  const voidM = useMutation({ mutationFn: () => voidRun(id!), onSuccess: () => { invalidate(); toast.success(t('run.voided')) }, onError: (e: any) => toast.error(e?.message || 'Failed') })

  if (isLoading || !run) {
    return <div className="flex items-center justify-center py-24 text-gray-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
  }

  const employeeDeductions = f(run.total_cpp_employee) + f(run.total_ei_employee) + f(run.total_federal_tax) + f(run.total_provincial_tax) + f(run.total_other_deductions)
  const employerCost = f(run.total_gross) + f(run.total_cpp_employer) + f(run.total_ei_employer)

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <Link to="/payroll" className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-2">
          <ArrowLeft className="w-3.5 h-3.5" /> {t('run.back')}
        </Link>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
                {formatDate(run.period_start)} – {formatDate(run.period_end)}
              </h1>
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[run.status]}`}>{t(`runs.status.${run.status}`)}</span>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {t('runs.payDate')}: {formatDate(run.pay_date)} · {t(`employees.fields.${run.pay_frequency}`)} · {t('runs.employees', { count: run.stubs.length })}
              {run.journal_entry_id && (
                <> · <Link to="/accounting/journal" className="inline-flex items-center gap-1 text-blue-600 hover:underline"><BookText className="w-3.5 h-3.5" /> {t('run.journal')}</Link></>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {run.status === 'draft' && (
              <button onClick={() => { if (confirm(t('run.approveConfirm'))) approve.mutate() }} disabled={approve.isPending} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <CheckCircle2 className="w-4 h-4" /> {t('run.approve')}
              </button>
            )}
            {run.status === 'approved' && (
              <button onClick={() => { if (confirm(t('run.markPaidConfirm'))) paid.mutate() }} disabled={paid.isPending} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
                <Banknote className="w-4 h-4" /> {t('run.markPaid')}
              </button>
            )}
            {run.status !== 'void' && (
              <button onClick={() => { if (confirm(t('run.voidConfirm'))) voidM.mutate() }} disabled={voidM.isPending} className="flex items-center gap-1.5 px-3 py-2 text-sm border border-red-200 dark:border-red-900 text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50">
                <Ban className="w-4 h-4" /> {t('run.void')}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <Tile label={t('run.totals.gross')} value={money(run.total_gross)} />
        <Tile label={t('run.totals.deductions')} value={`− ${money(employeeDeductions)}`} />
        <Tile label={t('run.totals.net')} value={money(run.total_net)} strong />
        <Tile label={t('run.totals.employer')} value={money(employerCost)} />
        <Tile label={t('run.totals.remit')} value={money(run.total_remittance)} accent />
      </div>

      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-500 dark:text-gray-400">
            <tr>
              <th className="text-left px-4 py-2 font-medium w-8" />
              <th className="text-left px-4 py-2 font-medium">{t('tabs.employees')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.hours')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('runs.gross')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.cpp')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.ei')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.fedTax')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.provTax')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('run.stub.net')}</th>
            </tr>
          </thead>
          <tbody>
            {run.stubs.map((s) => <StubRow key={s.id} s={s} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Tile({ label, value, strong, accent }: { label: string; value: string; strong?: boolean; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 ${accent ? 'border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-950/30' : 'border-gray-200 dark:border-gray-800'}`}>
      <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`tabular-nums mt-0.5 ${strong ? 'text-xl font-semibold text-gray-900 dark:text-gray-100' : 'text-lg text-gray-800 dark:text-gray-200'}`}>{value}</div>
    </div>
  )
}

function StubRow({ s }: { s: PayStub }) {
  const { t } = useTranslation('payroll')
  const [open, setOpen] = useState(false)
  const qc = s.province_of_employment === 'QC'
  const cpp = f(s.cpp_employee) + f(s.cpp2_employee)
  return (
    <>
      <tr className="border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50/60 dark:hover:bg-gray-900/40 cursor-pointer" onClick={() => setOpen((v) => !v)}>
        <td className="px-4 py-3 text-gray-400">{open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</td>
        <td className="px-4 py-3">
          <div className="font-medium text-gray-900 dark:text-gray-100">{s.employee_name}</div>
          <div className="text-xs text-gray-500 font-mono">{s.province_of_employment} · {t('run.stub.tables')} {s.tables_version}</div>
        </td>
        <td className="px-4 py-3 text-right tabular-nums">{s.hours ?? '—'}</td>
        <td className="px-4 py-3 text-right tabular-nums">{money(s.gross)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{money(cpp)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{money(f(s.ei_employee) + f(s.qpip_employee))}</td>
        <td className="px-4 py-3 text-right tabular-nums">{money(s.federal_tax)}</td>
        <td className="px-4 py-3 text-right tabular-nums">{money(s.provincial_tax)}</td>
        <td className="px-4 py-3 text-right tabular-nums font-medium">{money(s.net_pay)}</td>
      </tr>
      {open && (
        <tr className="bg-gray-50/50 dark:bg-gray-900/30">
          <td colSpan={9} className="px-6 py-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-3 text-sm">
              <Section title={t('runs.gross')}>
                <L k={t('run.stub.regular')} v={s.regular_pay} />
                <L k={t('run.stub.overtime')} v={s.overtime_pay} />
                <L k={t('run.stub.bonus')} v={s.bonus} />
                <L k={t('run.stub.vacation')} v={s.vacation_pay} />
                <L k={t('run.stub.other')} v={s.other_earnings} />
              </Section>
              <Section title={t('run.totals.deductions')}>
                <L k={qc ? t('run.stub.qpp') : t('run.stub.cpp')} v={s.cpp_employee} />
                <L k={t('run.stub.cpp2')} v={s.cpp2_employee} />
                <L k={t('run.stub.ei')} v={s.ei_employee} />
                {qc && <L k={t('run.stub.qpip')} v={s.qpip_employee} />}
                <L k={t('run.stub.fedTax')} v={s.federal_tax} />
                <L k={t('run.stub.provTax')} v={s.provincial_tax} />
                <L k={t('run.stub.otherDed')} v={s.other_deductions} />
              </Section>
              <Section title={t('run.totals.employer')}>
                <L k={t('run.stub.employerCpp')} v={f(s.cpp_employer) + f(s.cpp2_employer)} />
                <L k={t('run.stub.employerEi')} v={s.ei_employer} />
                {qc && <L k={t('run.stub.qpip')} v={s.qpip_employer} />}
              </Section>
              <Section title={t('run.stub.ytd')}>
                <L k={t('run.stub.ytdGross')} v={s.ytd_gross} />
                <L k={t('run.stub.cpp')} v={f(s.ytd_cpp_employee) + f(s.ytd_cpp2_employee)} />
                <L k={t('run.stub.ei')} v={s.ytd_ei_employee} />
                <L k={t('run.stub.fedTax')} v={s.ytd_federal_tax} />
                <L k={t('run.stub.provTax')} v={s.ytd_provincial_tax} />
                <L k={t('run.stub.ytdNet')} v={s.ytd_net} />
              </Section>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5">{title}</div>
      <dl className="space-y-0.5">{children}</dl>
    </div>
  )
}

function L({ k, v }: { k: string; v: string | number }) {
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (!n) return null
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-gray-600 dark:text-gray-400">{k}</dt>
      <dd className="tabular-nums text-gray-900 dark:text-gray-100">{money(n)}</dd>
    </div>
  )
}
