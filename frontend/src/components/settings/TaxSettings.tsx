import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, X, Check, Receipt, DollarSign, TrendingUp, TrendingDown } from 'lucide-react'
import {
  listTaxRates,
  createTaxRate,
  updateTaxRate,
  deleteTaxRate,
  getTaxLiability,
} from '@/api/tax'
import type { TaxRate } from '@/api/tax'

interface TaxRateFormData {
  name: string
  rate: number
  description: string
  is_default: boolean
  is_active: boolean
  region: string
}

const emptyForm: TaxRateFormData = {
  name: '',
  rate: 0,
  description: '',
  is_default: false,
  is_active: true,
  region: '',
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value)
}

export default function TaxSettings() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<TaxRateFormData>(emptyForm)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'success' | 'error'>('success')

  // Liability report date range
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

  const createMutation = useMutation({
    mutationFn: (formData: TaxRateFormData) =>
      createTaxRate({
        name: formData.name,
        rate: formData.rate,
        description: formData.description || undefined,
        is_default: formData.is_default,
        region: formData.region || undefined,
      }),
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
      updateTaxRate(id, {
        name: formData.name,
        rate: formData.rate,
        description: formData.description || undefined,
        is_default: formData.is_default,
        is_active: formData.is_active,
        region: formData.region || undefined,
      }),
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

  return (
    <div className="space-y-6">
      {/* Tax Rates Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Sales Tax Rates</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Configure tax rates for invoices and expenses.
            </p>
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
              Add Tax Rate
            </button>
          )}
        </div>

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

        {/* Tax Rate Form */}
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Sales Tax, VAT"
                  required
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rate (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.rate}
                  onChange={(e) => setForm({ ...form, rate: parseFloat(e.target.value) || 0 })}
                  required
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Region</label>
                <input
                  type="text"
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                  placeholder="e.g. California, NY"
                  className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional description"
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
                />
                Default rate
              </label>
              {editingId && (
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="rounded border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
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

        {/* Tax Rates Table */}
        {rates.length > 0 ? (
          <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
            <div className="px-5 py-3 border-b">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Configured Tax Rates ({rates.length})
              </h3>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 dark:bg-gray-950">
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Name</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Rate</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Region</th>
                  <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                  <th className="text-right px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rates.map((rate) => (
                  <tr key={rate.id} className="border-b last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Receipt className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                        <span className="text-gray-900 dark:text-gray-100 font-medium">{rate.name}</span>
                        {rate.is_default && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700">
                            Default
                          </span>
                        )}
                      </div>
                      {rate.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 ml-6">{rate.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-900 dark:text-gray-100 font-mono">{rate.rate}%</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{rate.region || '-'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          rate.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                        }`}
                      >
                        {rate.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => startEdit(rate)}
                          className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-blue-600 rounded hover:bg-blue-50"
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm('Delete this tax rate?')) {
                              deleteMutation.mutate(rate.id)
                            }
                          }}
                          disabled={deleteMutation.isPending}
                          className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 rounded hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
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
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Add tax rates to track sales tax on invoices and expenses.
            </p>
          </div>
        )}
      </div>

      {/* Tax Liability Report Section */}
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
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={() => refetchLiability()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Generate
            </button>
          </div>

          {liability && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-green-700 mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm font-medium">Tax Collected</span>
                </div>
                <p className="text-2xl font-semibold text-green-800">
                  {formatCurrency(liability.total_tax_collected)}
                </p>
                <p className="text-xs text-green-600 mt-1">From paid invoices</p>
              </div>
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-red-700 mb-1">
                  <TrendingDown className="w-4 h-4" />
                  <span className="text-sm font-medium">Tax Paid</span>
                </div>
                <p className="text-2xl font-semibold text-red-800">
                  {formatCurrency(liability.total_tax_paid)}
                </p>
                <p className="text-xs text-red-600 mt-1">From approved expenses</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-blue-700 mb-1">
                  <DollarSign className="w-4 h-4" />
                  <span className="text-sm font-medium">Net Liability</span>
                </div>
                <p className="text-2xl font-semibold text-blue-800">
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

      {/* Info section */}
      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">How Sales Tax Tracking Works</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>Tax rates can be applied when creating invoices or recording expenses</li>
          <li>Tax collected is calculated from the tax_amount on paid invoices</li>
          <li>Tax paid is calculated from the tax_amount on approved expenses</li>
          <li>Net liability = tax collected - tax paid (positive means you owe tax)</li>
          <li>Set one rate as "Default" to have it pre-selected on new invoices</li>
        </ul>
      </div>
    </div>
  )
}
