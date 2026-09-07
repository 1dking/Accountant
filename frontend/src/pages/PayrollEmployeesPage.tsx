import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Plus, Users, Loader2, Pencil, Trash2, X, Check, ArrowLeft, FileBadge } from 'lucide-react'
import {
  listEmployees, createEmployee, updateEmployee, deleteEmployee, downloadT4Pdf,
  type Employee, type EmployeeInput, type PayFrequency, type PayType,
} from '@/api/payroll'
import { listProvinces, type ProvinceInfo } from '@/api/tax'

const money = (n: string | number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(typeof n === 'string' ? parseFloat(n) : n)

const FREQS: PayFrequency[] = ['weekly', 'biweekly', 'semimonthly', 'monthly']

const emptyForm = (): EmployeeInput => ({
  first_name: '', last_name: '', email: '', sin: '', date_of_birth: null, hire_date: new Date().toISOString().slice(0, 10),
  job_title: '', province_of_employment: 'ON', pay_type: 'salary', pay_rate: 0, pay_frequency: 'biweekly',
  default_hours_per_period: 80, vacation_pay_pct: 4, vacation_pay_each_period: true,
  td1_federal_claim: null, td1_provincial_claim: null, additional_tax_per_period: 0, cpp_exempt: false, ei_exempt: false,
  address_line1: '', city: '', province: '', postal_code: '',
})

export default function PayrollEmployeesPage() {
  const { t } = useTranslation('payroll')
  const { t: tc } = useTranslation('common')
  const [showTerminated, setShowTerminated] = useState(false)
  const [editing, setEditing] = useState<Employee | 'new' | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['payroll-employees', showTerminated], queryFn: () => listEmployees(showTerminated) })
  const employees: Employee[] = data?.data ?? []

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Link to="/payroll" className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-2">
            <ArrowLeft className="w-3.5 h-3.5" /> {t('title')}
          </Link>
          <div className="flex items-center gap-2">
            <Users className="w-6 h-6 text-gray-700 dark:text-gray-300" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('employees.title')}</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-2xl">{t('employees.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input type="checkbox" checked={showTerminated} onChange={(e) => setShowTerminated(e.target.checked)} className="rounded" />
            {t('employees.showTerminated')}
          </label>
          <button onClick={() => setEditing('new')} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Plus className="w-4 h-4" /> {t('employees.add')}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : employees.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl">
          <Users className="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-600 dark:text-gray-300 font-medium">{t('employees.empty')}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('employees.emptyHint')}</p>
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-500 dark:text-gray-400">
              <tr>
                <th className="text-left px-4 py-2 font-medium">{t('employees.fields.firstName')} / {t('employees.fields.lastName')}</th>
                <th className="text-left px-4 py-2 font-medium">{t('employees.fields.provinceOfEmployment')}</th>
                <th className="text-right px-4 py-2 font-medium">{t('employees.fields.payRate')}</th>
                <th className="text-left px-4 py-2 font-medium">{t('employees.fields.frequency')}</th>
                <th className="text-right px-4 py-2 font-medium">{t('employees.fields.vacationBalance')}</th>
                <th className="text-left px-4 py-2 font-medium">{t('employees.fields.status')}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {employees.map((e) => (
                <EmployeeRow key={e.id} e={e} onEdit={() => setEditing(e)} t={t} tc={tc} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && <EmployeeModal employee={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

function EmployeeRow({ e, onEdit, t, tc }: { e: Employee; onEdit: () => void; t: any; tc: any }) {
  const qc = useQueryClient()
  const del = useMutation({
    mutationFn: () => deleteEmployee(e.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['payroll-employees'] }); toast.success(t('employees.removed')) },
    onError: (err: any) => toast.error(err?.message || tc('errors.generic')),
  })
  return (
    <tr className="border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50/60 dark:hover:bg-gray-900/40">
      <td className="px-4 py-3">
        <div className="font-medium text-gray-900 dark:text-gray-100">{e.full_name}</div>
        <div className="text-xs text-gray-500">{e.job_title || e.email || ''}{e.sin_masked ? ` · ${e.sin_masked}` : ''}</div>
      </td>
      <td className="px-4 py-3 font-mono text-xs">{e.province_of_employment}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {money(e.pay_rate)} <span className="text-xs text-gray-400">{e.pay_type === 'hourly' ? '/h' : '/yr'}</span>
      </td>
      <td className="px-4 py-3">{t(`employees.fields.${e.pay_frequency}`)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{money(e.vacation_accrued_balance)}</td>
      <td className="px-4 py-3">
        <span className={`text-[11px] px-1.5 py-0.5 rounded ${e.status === 'active' ? 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}`}>
          {t(`employees.fields.${e.status}`)}
        </span>
      </td>
      <td className="px-4 py-3 text-right whitespace-nowrap">
        <button
          onClick={() => downloadT4Pdf(e.id, new Date().getFullYear(), `T4-${new Date().getFullYear()}-${e.last_name.toLowerCase()}.pdf`).catch((err: any) => toast.error(err?.message || tc('errors.generic')))}
          className="p-1.5 text-gray-400 hover:text-blue-600 rounded hover:bg-blue-50 dark:hover:bg-blue-950" title={`${t('t4.download')} ${new Date().getFullYear()}`}
        ><FileBadge className="w-4 h-4" /></button>
        <button onClick={onEdit} className="p-1.5 text-gray-400 hover:text-blue-600 rounded hover:bg-blue-50 dark:hover:bg-blue-950" title={tc('actions.edit')}><Pencil className="w-4 h-4" /></button>
        <button onClick={() => { if (confirm(`${tc('actions.delete')} ${e.full_name}?`)) del.mutate() }} disabled={del.isPending} className="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-red-50 dark:hover:bg-red-950" title={tc('actions.delete')}><Trash2 className="w-4 h-4" /></button>
      </td>
    </tr>
  )
}

function EmployeeModal({ employee, onClose }: { employee: Employee | null; onClose: () => void }) {
  const { t } = useTranslation('payroll')
  const { t: tc } = useTranslation('common')
  const qc = useQueryClient()
  const [form, setForm] = useState<EmployeeInput>(() => employee ? {
    first_name: employee.first_name, last_name: employee.last_name, email: employee.email ?? '', phone: employee.phone ?? '',
    sin: '', date_of_birth: employee.date_of_birth, hire_date: employee.hire_date, job_title: employee.job_title ?? '',
    province_of_employment: employee.province_of_employment, pay_type: employee.pay_type, pay_rate: parseFloat(employee.pay_rate),
    pay_frequency: employee.pay_frequency, default_hours_per_period: employee.default_hours_per_period ? parseFloat(employee.default_hours_per_period) : null,
    vacation_pay_pct: parseFloat(employee.vacation_pay_pct), vacation_pay_each_period: employee.vacation_pay_each_period,
    td1_federal_claim: employee.td1_federal_claim ? parseFloat(employee.td1_federal_claim) : null,
    td1_provincial_claim: employee.td1_provincial_claim ? parseFloat(employee.td1_provincial_claim) : null,
    additional_tax_per_period: parseFloat(employee.additional_tax_per_period), cpp_exempt: employee.cpp_exempt, ei_exempt: employee.ei_exempt,
    address_line1: employee.address_line1 ?? '', city: employee.city ?? '', province: employee.province ?? '', postal_code: employee.postal_code ?? '',
  } : emptyForm())

  const { data: provData } = useQuery({ queryKey: ['tax-provinces'], queryFn: listProvinces })
  const provinces: ProvinceInfo[] = provData?.data ?? []

  const save = useMutation({
    mutationFn: () => {
      const payload: any = { ...form }
      for (const k of ['email', 'phone', 'sin', 'job_title', 'address_line1', 'city', 'province', 'postal_code']) if (payload[k] === '') payload[k] = null
      if (!payload.sin) delete payload.sin
      return employee ? updateEmployee(employee.id, payload) : createEmployee(payload)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['payroll-employees'] }); toast.success(t('employees.saved')); onClose() },
    onError: (err: any) => toast.error(err?.message || t('employees.saveFailed')),
  })

  const set = (k: keyof EmployeeInput, v: any) => setForm((f) => ({ ...f, [k]: v }))
  const inp = 'w-full px-3 py-2 border rounded-md text-sm bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500'
  const lab = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate() }}
        className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-2xl p-6 space-y-5 my-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{employee ? t('employees.edit') : t('employees.add')}</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className={lab}>{t('employees.fields.firstName')}</label><input required className={inp} value={form.first_name} onChange={(e) => set('first_name', e.target.value)} /></div>
          <div><label className={lab}>{t('employees.fields.lastName')}</label><input required className={inp} value={form.last_name} onChange={(e) => set('last_name', e.target.value)} /></div>
          <div><label className={lab}>{t('employees.fields.email')}</label><input type="email" className={inp} value={form.email ?? ''} onChange={(e) => set('email', e.target.value)} /></div>
          <div><label className={lab}>{t('employees.fields.jobTitle')}</label><input className={inp} value={form.job_title ?? ''} onChange={(e) => set('job_title', e.target.value)} /></div>
          <div>
            <label className={lab}>{t('employees.fields.sin')}</label>
            <input className={`${inp} font-mono`} inputMode="numeric" placeholder={employee?.sin_masked ?? '123 456 789'} value={form.sin ?? ''} onChange={(e) => set('sin', e.target.value)} />
            <p className="text-[11px] text-gray-500 mt-1">{t('employees.fields.sinHint')}</p>
          </div>
          <div>
            <label className={lab}>{t('employees.fields.dob')}</label>
            <input type="date" className={inp} value={form.date_of_birth ?? ''} onChange={(e) => set('date_of_birth', e.target.value || null)} />
            <p className="text-[11px] text-gray-500 mt-1">{t('employees.fields.dobHint')}</p>
          </div>
          <div><label className={lab}>{t('employees.fields.hireDate')}</label><input type="date" required className={inp} value={form.hire_date} onChange={(e) => set('hire_date', e.target.value)} /></div>
          <div>
            <label className={lab}>{t('employees.fields.provinceOfEmployment')}</label>
            <select className={inp} value={form.province_of_employment} onChange={(e) => set('province_of_employment', e.target.value)}>
              {provinces.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </select>
            <p className="text-[11px] text-gray-500 mt-1">{t('employees.fields.provinceHint')}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-gray-100 dark:border-gray-800">
          <div>
            <label className={lab}>{t('employees.fields.payType')}</label>
            <select className={inp} value={form.pay_type} onChange={(e) => set('pay_type', e.target.value as PayType)}>
              <option value="salary">{t('employees.fields.salary')}</option>
              <option value="hourly">{t('employees.fields.hourly')}</option>
            </select>
          </div>
          <div>
            <label className={lab}>{t('employees.fields.payRate')} <span className="text-gray-400">({form.pay_type === 'hourly' ? t('employees.fields.rateHourly') : t('employees.fields.rateSalary')})</span></label>
            <input type="number" step="0.01" min="0" required className={`${inp} tabular-nums`} value={form.pay_rate || ''} onChange={(e) => set('pay_rate', parseFloat(e.target.value) || 0)} />
          </div>
          <div>
            <label className={lab}>{t('employees.fields.frequency')}</label>
            <select className={inp} value={form.pay_frequency} onChange={(e) => set('pay_frequency', e.target.value as PayFrequency)}>
              {FREQS.map((f) => <option key={f} value={f}>{t(`employees.fields.${f}`)}</option>)}
            </select>
          </div>
          <div>
            <label className={lab}>{t('employees.fields.defaultHours')}</label>
            <input type="number" step="0.25" min="0" className={`${inp} tabular-nums`} disabled={form.pay_type !== 'hourly'} value={form.default_hours_per_period ?? ''} onChange={(e) => set('default_hours_per_period', e.target.value === '' ? null : parseFloat(e.target.value))} />
          </div>
          <div>
            <label className={lab}>{t('employees.fields.vacationPct')}</label>
            <input type="number" step="0.01" min="0" max="20" className={`${inp} tabular-nums`} value={form.vacation_pay_pct ?? 4} onChange={(e) => set('vacation_pay_pct', parseFloat(e.target.value) || 0)} />
          </div>
          <div className="col-span-2 sm:col-span-3 flex flex-col justify-end gap-1.5">
            <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="radio" checked={!!form.vacation_pay_each_period} onChange={() => set('vacation_pay_each_period', true)} /> {t('employees.fields.vacationEachPeriod')}</label>
            <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="radio" checked={!form.vacation_pay_each_period} onChange={() => set('vacation_pay_each_period', false)} /> {t('employees.fields.vacationAccrue')}</label>
          </div>
        </div>

        <details className="pt-2 border-t border-gray-100 dark:border-gray-800">
          <summary className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">TD1 &amp; exemptions</summary>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-3">
            <div><label className={lab}>{t('employees.fields.td1Federal')}</label><input type="number" step="1" className={`${inp} tabular-nums`} value={form.td1_federal_claim ?? ''} onChange={(e) => set('td1_federal_claim', e.target.value === '' ? null : parseFloat(e.target.value))} /></div>
            <div><label className={lab}>{t('employees.fields.td1Provincial')}</label><input type="number" step="1" className={`${inp} tabular-nums`} value={form.td1_provincial_claim ?? ''} onChange={(e) => set('td1_provincial_claim', e.target.value === '' ? null : parseFloat(e.target.value))} /></div>
            <div><label className={lab}>{t('employees.fields.additionalTax')}</label><input type="number" step="0.01" min="0" className={`${inp} tabular-nums`} value={form.additional_tax_per_period ?? 0} onChange={(e) => set('additional_tax_per_period', parseFloat(e.target.value) || 0)} /></div>
            <p className="col-span-full text-[11px] text-gray-500 -mt-2">{t('employees.fields.td1Hint')}</p>
            <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={!!form.cpp_exempt} onChange={(e) => set('cpp_exempt', e.target.checked)} /> {t('employees.fields.cppExempt')}</label>
            <label className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={!!form.ei_exempt} onChange={(e) => set('ei_exempt', e.target.checked)} /> {t('employees.fields.eiExempt')}</label>
          </div>
        </details>

        <details className="pt-2 border-t border-gray-100 dark:border-gray-800">
          <summary className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer">{t('employees.fields.address')}</summary>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-3">
            <div className="col-span-2"><input className={inp} placeholder={t('employees.fields.address')} value={form.address_line1 ?? ''} onChange={(e) => set('address_line1', e.target.value)} /></div>
            <div><input className={inp} placeholder={t('employees.fields.city')} value={form.city ?? ''} onChange={(e) => set('city', e.target.value)} /></div>
            <div className="flex gap-2">
              <input className={`${inp} font-mono uppercase`} maxLength={2} placeholder={t('employees.fields.province')} value={form.province ?? ''} onChange={(e) => set('province', e.target.value.toUpperCase())} />
              <input className={`${inp} font-mono uppercase`} maxLength={7} placeholder={t('employees.fields.postal')} value={form.postal_code ?? ''} onChange={(e) => set('postal_code', e.target.value.toUpperCase())} />
            </div>
          </div>
        </details>

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">{tc('actions.cancel')}</button>
          <button type="submit" disabled={save.isPending} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Check className="w-4 h-4" /> {save.isPending ? tc('actions.saving') : tc('actions.save')}
          </button>
        </div>
      </form>
    </div>
  )
}
