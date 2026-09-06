import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Pencil, Trash2, X, Check, Receipt, DollarSign, TrendingUp, TrendingDown, MapPin, Lock } from 'lucide-react'
import {
  listTaxRates,
  listProvinces,
  createTaxRate,
  updateTaxRate,
  deleteTaxRate,
  getTaxLiability,
} from '@/api/tax'
import type { TaxRate, TaxType, ProvinceInfo } from '@/api/tax'
import { getCompanySettings, updateCompanySettings } from '@/api/settings'

interface TaxRateFormData {
  name: string
  rate: number
  description: string
  is_default: boolean
  is_active: boolean
  region: string
  tax_type: TaxType | ''
  province: string
  is_recoverable: boolean
}

const emptyForm: TaxRateFormData = {
  name: '',
  rate: 0,
  description: '',
  is_default: false,
  is_active: true,
  region: '',
  tax_type: '',
  province: '',
  is_recoverable: true,
}

interface ProvinceFormData {
  province: string
  business_number: string
  gst_hst_number: string
  fiscal_year_end_month: number | ''
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
  }).format(value)
}

const TAX_TYPES: TaxType[] = ['gst', 'hst', 'pst', 'rst', 'qst', 'other']

export default function TaxSettings() {
  const { t } = useTranslation('tax')
  const { t: tc } = useTranslation('common')
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<TaxRateFormData>(emptyForm)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'success' | 'error'>('success')

  // ── Province / CRA identity ──
  const [provinceForm, setProvinceForm] = useState<ProvinceFormData>({
    province: '',
    business_number: '',
    gst_hst_number: '',
    fiscal_year_end_month: '',
  })

  const { data: companyData } = useQuery({
    queryKey: ['company-settings'],
    queryFn: getCompanySettings,
  })
  const { data: provincesData } = useQuery({
    queryKey: ['tax-provinces'],
    queryFn: listProvinces,
  })
  const provinces: ProvinceInfo[] = provincesData?.data ?? []
  const company = companyData?.data ?? null

  useEffect(() => {
    if (!company) return
    setProvinceForm({
      province: company.province ?? '',
      business_number: company.business_number ?? '',
      gst_hst_number: company.gst_hst_number ?? '',
      fiscal_year_end_month: company.fiscal_year_end_month ?? '',
    })
  }, [company])

  const selectedProvince = provinces.find((p) => p.code === provinceForm.province) ?? null

  const saveProvinceMutation = useMutation({
    mutationFn: () =>
      updateCompanySettings({
        province: provinceForm.province || null,
        business_number: provinceForm.business_number || null,
        gst_hst_number: provinceForm.gst_hst_number || null,
        fiscal_year_end_month:
          provinceForm.fiscal_year_end_month === '' ? null : Number(provinceForm.fiscal_year_end_month),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-settings'] })
      queryClient.invalidateQueries({ queryKey: ['tax-rates'] })
      showMessage(t('province.saved', { regime: selectedProvince?.regime ?? '' }))
    },
    onError: () => showMessage(t('province.saveFailed'), 'error'),
  })

  // ── Liability report date range ──
  const today = new Date()
  const startOfYear = `${today.getFullYear()}-01-01`
  const todayStr = today.toISOString().slice(0, 10)
  const [dateFrom, setDateFrom] = useState(startOfYear)
  const [dateTo, setDateTo] = useState(todayStr)

  const { data: ratesData } = useQuery({
    queryKey: ['tax-rates'],
    queryFn: listTaxRates,
  })

  const { data: liabilityData, refetch: refetchLiability } = useQuery({
    queryKey: ['tax-liability', dateFrom, dateTo],
    queryFn: () => getTaxLiability(dateFrom, dateTo),
  })

  const rates: TaxRate[] = ratesData?.data ?? []
  const liability = liabilityData?.data ?? null

  function showMessage(text: string, type: 'success' | 'error' = 'success') {
    setMsg(text)
    setMsgType(type)
    setTimeout(() => setMsg(''), 4000)
  }

  function ratePayload(formData: TaxRateFormData) {
    return {
      name: formData.name,
      rate: formData.rate,
      description: formData.description || undefined,
      is_default: formData.is_default,
      region: formData.region || undefined,
      tax_type: formData.tax_type || undefined,
      province: formData.province || undefined,
      is_recoverable: formData.is_recoverable,
    }
  }

  const createMutation = useMutation({
    mutationFn: (formData: TaxRateFormData) => createTaxRate(ratePayload(formData)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tax-rates'] })
      setShowForm(false)
      setForm(emptyForm)
      showMessage('Tax rate created')
    },
    onError: () => showMessage('Failed to create tax rate', 'error'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: TaxRateFormData }) =>
      updateTaxRate(id, { ...ratePayload(formData), is_active: formData.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tax-rates'] })
      setShowForm(false)
      setEditingId(null)
      setForm(emptyForm)
      showMessage('Tax rate updated')
    },
    onError: () => showMessage('Failed to update tax rate', 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTaxRate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tax-rates'] })
      showMessage('Tax rate deleted')
    },
    onError: () => showMessage('Failed to delete tax rate', 'error'),
  })

  function startEdit(rate: TaxRate) {
    setEditingId(rate.id)
    setForm({
      name: rate.name,
      rate: rate.rate,
      description: rate.description || '',
      is_default: rate.is_default,
      is_active: rate.is_active,
      region: rate.region || '',
      tax_type: rate.tax_type ?? '',
      province: rate.province ?? '',
      is_recoverable: rate.is_recoverable,
    })
    setShowForm(true)
  }

  function cancelForm() {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editingId) {
      updateMutation.mutate({ id: editingId, formData: form })
    } else {
      createMutation.mutate(form)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending
  const inputCls =
    'w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-900'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'

  return (
    <div className="space-y-6">
      {msg && (
        <div
          className={`border rounded-lg p-3 text-sm ${
            msgType === 'success'
              ? 'bg-green-50 dark:bg-green-900/30 border-green-200 text-green-700'
              : 'bg-red-50 dark:bg-red-900/30 border-red-200 text-red-700'
          }`}
        >
          {msg}
        </div>
      )}

      {/* ── Province & CRA identity ── */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('province.title')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('province.subtitle')}</p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            saveProvinceMutation.mutate()
          }}
          className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>{t('province.label')}</label>
              <div className="relative">
                <MapPin className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <select
                  value={provinceForm.province}
                  onChange={(e) => setProvinceForm({ ...provinceForm, province: e.target.value })}
                  className={`${inputCls} pl-9`}
                >
                  <option value="">{t('province.placeholder')}</option>
                  {provinces.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.name} — {p.regime}
                    </option>
                  ))}
                </select>
              </div>
              {selectedProvince && (
                <p className="text-xs text-blue-700 dark:text-blue-300 mt-1.5 font-medium">
                  {t('province.regime', { regime: selectedProvince.regime })}
                </p>
              )}
            </div>
            <div>
              <label className={labelCls}>{t('province.fiscalYearEnd')}</label>
              <select
                value={provinceForm.fiscal_year_end_month}
                onChange={(e) =>
                  setProvinceForm({
                    ...provinceForm,
                    fiscal_year_end_month: e.target.value === '' ? '' : Number(e.target.value),
                  })
                }
                className={inputCls}
              >
                <option value="">—</option>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>
                    {t(`months.${m}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls}>{t('province.businessNumber')}</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={9}
                value={provinceForm.business_number}
                onChange={(e) => setProvinceForm({ ...provinceForm, business_number: e.target.value })}
                placeholder="123456789"
                className={`${inputCls} font-mono`}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('province.businessNumberHint')}</p>
            </div>
            <div>
              <label className={labelCls}>{t('province.gstNumber')}</label>
              <input
                type="text"
                maxLength={15}
                value={provinceForm.gst_hst_number}
                onChange={(e) => setProvinceForm({ ...provinceForm, gst_hst_number: e.target.value.toUpperCase() })}
                placeholder="123456789RT0001"
                className={`${inputCls} font-mono`}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('province.gstNumberHint')}</p>
            </div>
          </div>
          <div>
            <button
              type="submit"
              disabled={saveProvinceMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              {saveProvinceMutation.isPending ? tc('actions.saving') : tc('actions.save')}
            </button>
          </div>
        </form>
      </div>

      {/* ── Tax Rates ── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('rates.title')}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('rates.subtitle')}</p>
          </div>
          {!showForm && (
            <button
              onClick={() => {
                setForm(emptyForm)
                setEditingId(null)
                setShowForm(true)
              }}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              {t('rates.addCustom')}
            </button>
          )}
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingId ? 'Edit Tax Rate' : 'New Tax Rate'}
              </h3>
              <button type="button" onClick={cancelForm} className="text-gray-400 dark:text-gray-500 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className={labelCls}>Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Sales Tax, VAT"
                  required
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>Rate (%)</label>
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  max="100"
                  value={form.rate}
                  onChange={(e) => setForm({ ...form, rate: parseFloat(e.target.value) || 0 })}
                  required
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>{t('rates.type')}</label>
                <select
                  value={form.tax_type}
                  onChange={(e) => setForm({ ...form, tax_type: e.target.value as TaxType | '' })}
                  className={inputCls}
                >
                  <option value="">—</option>
                  {TAX_TYPES.map((tt) => (
                    <option key={tt} value={tt}>
                      {tt.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>{t('rates.province')}</label>
                <select
                  value={form.province}
                  onChange={(e) => setForm({ ...form, province: e.target.value })}
                  className={inputCls}
                >
                  <option value="">{t('rates.federal')}</option>
                  {provinces.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <label className={labelCls}>Description</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Optional description"
                  className={inputCls}
                />
              </div>
            </div>

            <div className="flex items-center gap-6 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                Default rate
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_recoverable}
                  onChange={(e) => setForm({ ...form, is_recoverable: e.target.checked })}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                {t('rates.recoverable')}
              </label>
              {editingId && (
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                  />
                  Active
                </label>
              )}
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={isPending || !form.name}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                {isPending ? 'Saving...' : editingId ? 'Update Rate' : 'Create Rate'}
              </button>
              <button
                type="button"
                onClick={cancelForm}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {rates.length > 0 ? (
          <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 dark:bg-gray-950">
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Name</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Rate</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('rates.type')}</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('rates.province')}</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                  <th className="text-right px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rates.map((rate) => (
                  <tr key={rate.id} className="border-b last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        {rate.is_system ? (
                          <Lock className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                        ) : (
                          <Receipt className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                        )}
                        <span className="text-gray-900 dark:text-gray-100 font-medium">{rate.name}</span>
                        {rate.is_system && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                            {tc('status.system')}
                          </span>
                        )}
                        {rate.is_default && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700">
                            {tc('status.default')}
                          </span>
                        )}
                        {!rate.is_recoverable && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200">
                            {t('rates.nonRecoverable')}
                          </span>
                        )}
                      </div>
                      {rate.description && !rate.is_system && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 ml-6">{rate.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-900 dark:text-gray-100 font-mono tabular-nums">{rate.rate}%</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 uppercase text-xs font-mono">
                      {rate.tax_type ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {rate.province ?? (rate.tax_type ? t('rates.federal') : rate.region || '—')}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          rate.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                        }`}
                      >
                        {rate.is_active ? tc('status.active') : tc('status.inactive')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {rate.is_system ? (
                        <span className="text-xs text-gray-400 dark:text-gray-500" title={t('rates.systemHint')}>
                          —
                        </span>
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => startEdit(rate)}
                            className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-blue-600 rounded hover:bg-blue-50"
                            title={tc('actions.edit')}
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => {
                              if (confirm('Delete this tax rate?')) deleteMutation.mutate(rate.id)
                            }}
                            disabled={deleteMutation.isPending}
                            className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 rounded hover:bg-red-50"
                            title={tc('actions.delete')}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-900 border rounded-lg p-8 text-center text-gray-500 dark:text-gray-400">
            <Receipt className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">No tax rates configured yet.</p>
          </div>
        )}
      </div>

      {/* ── Tax Liability Report ── */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Tax Liability Report</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            View the net sales tax liability for a given period.
          </p>
        </div>

        <div className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4">
          <div className="flex flex-col sm:flex-row items-end gap-4">
            <div className="flex-1">
              <label className={labelCls}>From</label>
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={inputCls} />
            </div>
            <div className="flex-1">
              <label className={labelCls}>To</label>
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={inputCls} />
            </div>
            <button
              onClick={() => refetchLiability()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              {tc('actions.generate')}
            </button>
          </div>

          {liability && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-green-700 mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm font-medium">Tax Collected</span>
                </div>
                <p className="text-2xl font-semibold text-green-800 tabular-nums">
                  {formatCurrency(liability.total_tax_collected)}
                </p>
                <p className="text-xs text-green-600 mt-1">From paid invoices</p>
              </div>
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-700 mb-1">
                  <TrendingDown className="w-4 h-4" />
                  <span className="text-sm font-medium">Tax Paid</span>
                </div>
                <p className="text-2xl font-semibold text-red-800 tabular-nums">
                  {formatCurrency(liability.total_tax_paid)}
                </p>
                <p className="text-xs text-red-600 mt-1">From approved expenses</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-blue-700 mb-1">
                  <DollarSign className="w-4 h-4" />
                  <span className="text-sm font-medium">Net Liability</span>
                </div>
                <p className="text-2xl font-semibold text-blue-800 tabular-nums">
                  {formatCurrency(liability.net_tax_liability)}
                </p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                  {liability.net_tax_liability >= 0 ? 'Amount owed' : 'Credit / refund due'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
