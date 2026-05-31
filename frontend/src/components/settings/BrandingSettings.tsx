import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, Trash2, Loader2, Building2, Palette } from 'lucide-react'
import { api } from '@/api/client'
import { brandingApi } from '@/api/branding'
import {
  getCompanySettings,
  updateCompanySettings,
  uploadLogo,
  deleteLogo,
  getLogoUrl,
} from '@/api/settings'
import type { CompanySettings } from '@/api/settings'
import type { BrandingSettings as BrandingModel } from '@/types/models'

const CURRENCY_OPTIONS = [
  { value: 'CAD', label: 'CAD - Canadian Dollar' },
  { value: 'USD', label: 'USD - US Dollar' },
  { value: 'EUR', label: 'EUR - Euro' },
  { value: 'GBP', label: 'GBP - British Pound' },
]

const ACCEPTED_IMAGE_TYPES = '.png,.jpg,.jpeg,.svg,.webp'

export default function BrandingSettings() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'success' | 'error'>('success')

  const [form, setForm] = useState({
    company_name: '',
    company_email: '',
    company_phone: '',
    company_website: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    zip_code: '',
    country: '',
    default_currency: 'CAD',
    default_tax_rate_id: '',
  })

  // Commit 26 — brand visual identity (separate from the boring
  // company-info form above). Writes to the BrandingSettings model
  // (logo_url, primary_color, accent_color). The BrandThemeProvider
  // mounted at the App root sets CSS variables from these values so
  // sidebar accents + primary CTAs follow the brand color.
  const [brandForm, setBrandForm] = useState({
    logo_url: '',
    primary_color: '#2563eb',
    accent_color: '#f59e0b',
  })

  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ['company-settings'],
    queryFn: getCompanySettings,
  })

  const settings = settingsData?.data

  const { data: brandingResp } = useQuery({
    queryKey: ['branding'],
    queryFn: () => brandingApi.get() as Promise<{ data: BrandingModel | null }>,
  })
  const branding = brandingResp?.data ?? null

  const { data: taxRatesData } = useQuery({
    queryKey: ['tax-rates'],
    queryFn: () => api.get<{ data: { id: string; name: string; rate: number }[] }>('/accounting/tax-rates'),
  })
  const taxRates = taxRatesData?.data ?? []

  // Populate form when settings load
  useEffect(() => {
    if (settings) {
      setForm({
        company_name: settings.company_name ?? '',
        company_email: settings.company_email ?? '',
        company_phone: settings.company_phone ?? '',
        company_website: settings.company_website ?? '',
        address_line1: settings.address_line1 ?? '',
        address_line2: settings.address_line2 ?? '',
        city: settings.city ?? '',
        state: settings.state ?? '',
        zip_code: settings.zip_code ?? '',
        country: settings.country ?? '',
        default_currency: settings.default_currency ?? 'CAD',
        default_tax_rate_id: settings.default_tax_rate_id ?? '',
      })
    }
  }, [settings])

  // Populate brand visual identity form when branding loads.
  useEffect(() => {
    if (branding) {
      setBrandForm({
        logo_url: branding.logo_url ?? '',
        primary_color: branding.primary_color || '#2563eb',
        accent_color: branding.accent_color || '#f59e0b',
      })
    }
  }, [branding])

  const showMessage = (text: string, type: 'success' | 'error') => {
    setMsg(text)
    setMsgType(type)
    setTimeout(() => setMsg(''), 4000)
  }

  const saveMutation = useMutation({
    mutationFn: (data: Partial<CompanySettings>) => updateCompanySettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-settings'] })
      showMessage('Company settings saved', 'success')
    },
    onError: () => {
      showMessage('Failed to save settings', 'error')
    },
  })

  const brandMutation = useMutation({
    mutationFn: (data: Partial<BrandingModel>) =>
      brandingApi.update(data as Record<string, unknown>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['branding'] })
      queryClient.invalidateQueries({ queryKey: ['branding-public'] })
      showMessage('Brand visuals saved', 'success')
    },
    onError: () => {
      showMessage('Failed to save brand visuals', 'error')
    },
  })

  const handleBrandSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    brandMutation.mutate({
      logo_url: brandForm.logo_url || undefined,
      primary_color: brandForm.primary_color,
      accent_color: brandForm.accent_color,
    })
  }

  const updateBrandField = (field: 'logo_url' | 'primary_color' | 'accent_color', value: string) => {
    setBrandForm((prev) => ({ ...prev, [field]: value }))
  }

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadLogo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-settings'] })
      showMessage('Logo uploaded', 'success')
    },
    onError: () => {
      showMessage('Failed to upload logo', 'error')
    },
  })

  const deleteLogoMutation = useMutation({
    mutationFn: deleteLogo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-settings'] })
      showMessage('Logo removed', 'success')
    },
    onError: () => {
      showMessage('Failed to remove logo', 'error')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const updates: Partial<CompanySettings> = {
      company_name: form.company_name || null,
      company_email: form.company_email || null,
      company_phone: form.company_phone || null,
      company_website: form.company_website || null,
      address_line1: form.address_line1 || null,
      address_line2: form.address_line2 || null,
      city: form.city || null,
      state: form.state || null,
      zip_code: form.zip_code || null,
      country: form.country || null,
      default_currency: form.default_currency,
      default_tax_rate_id: form.default_tax_rate_id || null,
    }
    saveMutation.mutate(updates)
  }

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadMutation.mutate(file)
    }
    // Reset file input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleDeleteLogo = () => {
    if (confirm('Remove the company logo?')) {
      deleteLogoMutation.mutate()
    }
  }

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const hasLogo = !!settings?.logo_storage_path
  const isUploading = uploadMutation.isPending || deleteLogoMutation.isPending

  if (settingsLoading) {
    return (
      <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400 dark:text-gray-500" />
        </div>
      </section>
    )
  }

  return (
    <section className="bg-white dark:bg-gray-900 border rounded-lg p-6">
      <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-6">Company Branding</h2>

      {msg && (
        <div
          className={`mb-4 rounded-lg p-3 text-sm ${
            msgType === 'success'
              ? 'bg-green-50 dark:bg-green-900/30 border border-green-200 text-green-700'
              : 'bg-red-50 dark:bg-red-900/30 border border-red-200 text-red-700'
          }`}
        >
          {msg}
        </div>
      )}

      {/* Commit 26 — Brand Visual Identity. Writes to BrandingSettings
          (separate from the company logo which is for documents/invoices).
          BrandThemeProvider reads --brand-primary from these values on
          app load and propagates them through the sidebar + primary CTAs. */}
      <form onSubmit={handleBrandSubmit} className="mb-10 p-5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950">
        <div className="flex items-center gap-2 mb-4">
          <Palette className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Brand Visual Identity</h3>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-5">
          These values theme the whole platform — sidebar wordmark, primary buttons, accents.
          Guests on your meeting share links also see them. (Tier-gating coming later.)
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Brand Logo URL
            </label>
            <input
              type="url"
              value={brandForm.logo_url}
              onChange={(e) => updateBrandField('logo_url', e.target.value)}
              placeholder="https://yourcompany.com/logo.png"
              className="w-full px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Hosted PNG/SVG/WebP. Used by sidebar, login screen, meeting invites, and the guest knock page.
              Leave blank to fall back to the company name as text.
            </p>
            {brandForm.logo_url && (
              <div className="mt-3 inline-flex items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3">
                <img
                  src={brandForm.logo_url}
                  alt="Brand logo preview"
                  className="h-10 max-w-[180px] object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Primary Color
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={brandForm.primary_color}
                  onChange={(e) => updateBrandField('primary_color', e.target.value)}
                  className="h-10 w-12 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                />
                <input
                  type="text"
                  value={brandForm.primary_color}
                  onChange={(e) => updateBrandField('primary_color', e.target.value)}
                  placeholder="#2563eb"
                  className="flex-1 px-3 py-2 text-sm font-mono border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Sidebar active state, primary buttons, links.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Accent Color
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={brandForm.accent_color}
                  onChange={(e) => updateBrandField('accent_color', e.target.value)}
                  className="h-10 w-12 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                />
                <input
                  type="text"
                  value={brandForm.accent_color}
                  onChange={(e) => updateBrandField('accent_color', e.target.value)}
                  placeholder="#f59e0b"
                  className="flex-1 px-3 py-2 text-sm font-mono border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Secondary highlights, badges, hover states.
              </p>
            </div>
          </div>

          {/* Live preview */}
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Preview</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                style={{ background: brandForm.primary_color }}
                className="px-3 py-1.5 text-sm font-medium text-white rounded-md"
              >
                Primary button
              </button>
              <span
                style={{ background: brandForm.accent_color, color: 'white' }}
                className="px-2 py-0.5 text-xs font-medium rounded"
              >
                Accent badge
              </span>
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                style={{ color: brandForm.primary_color }}
                className="text-sm font-medium underline"
              >
                Themed link
              </a>
            </div>
          </div>

          <button
            type="submit"
            disabled={brandMutation.isPending}
            style={{ background: brandForm.primary_color }}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-md disabled:opacity-50 hover:opacity-90 transition"
          >
            {brandMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Save brand visuals
          </button>
        </div>
      </form>

      {/* Logo Section */}
      <div className="mb-8">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Company Logo</h3>
        <div className="flex items-center gap-4">
          <div className="w-24 h-24 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 flex items-center justify-center overflow-hidden bg-gray-50 dark:bg-gray-950">
            {hasLogo ? (
              <img
                src={getLogoUrl()}
                alt="Company logo"
                className="w-full h-full object-contain"
              />
            ) : (
              <Building2 className="w-8 h-8 text-gray-300" />
            )}
          </div>
          <div className="flex flex-col gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES}
              onChange={handleLogoUpload}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
            >
              {uploadMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {hasLogo ? 'Replace Logo' : 'Upload Logo'}
            </button>
            {hasLogo && (
              <button
                type="button"
                onClick={handleDeleteLogo}
                disabled={isUploading}
                className="flex items-center gap-1.5 px-3 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50"
              >
                {deleteLogoMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Remove Logo
              </button>
            )}
            <p className="text-xs text-gray-400 dark:text-gray-500">PNG, JPG, SVG, or WebP. Recommended 200x200px.</p>
          </div>
        </div>
      </div>

      {/* Settings Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Company Info */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Company Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Company Name</label>
              <input
                type="text"
                value={form.company_name}
                onChange={(e) => updateField('company_name', e.target.value)}
                placeholder="Your Company Inc."
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
              <input
                type="email"
                value={form.company_email}
                onChange={(e) => updateField('company_email', e.target.value)}
                placeholder="info@company.com"
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
              <input
                type="tel"
                value={form.company_phone}
                onChange={(e) => updateField('company_phone', e.target.value)}
                placeholder="+1 (555) 123-4567"
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Website</label>
              <input
                type="url"
                value={form.company_website}
                onChange={(e) => updateField('company_website', e.target.value)}
                placeholder="https://company.com"
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Address */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Address</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Address Line 1</label>
              <input
                type="text"
                value={form.address_line1}
                onChange={(e) => updateField('address_line1', e.target.value)}
                placeholder="123 Main Street"
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Address Line 2</label>
              <input
                type="text"
                value={form.address_line2}
                onChange={(e) => updateField('address_line2', e.target.value)}
                placeholder="Suite 100"
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">City</label>
                <input
                  type="text"
                  value={form.city}
                  onChange={(e) => updateField('city', e.target.value)}
                  placeholder="Toronto"
                  className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">State / Province</label>
                <input
                  type="text"
                  value={form.state}
                  onChange={(e) => updateField('state', e.target.value)}
                  placeholder="Ontario"
                  className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">ZIP / Postal Code</label>
                <input
                  type="text"
                  value={form.zip_code}
                  onChange={(e) => updateField('zip_code', e.target.value)}
                  placeholder="M5V 1A1"
                  className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Country</label>
                <input
                  type="text"
                  value={form.country}
                  onChange={(e) => updateField('country', e.target.value)}
                  placeholder="Canada"
                  className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Defaults */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Defaults</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Default Currency</label>
              <select
                value={form.default_currency}
                onChange={(e) => updateField('default_currency', e.target.value)}
                className="w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {CURRENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Default Tax Rate</label>
              <select
                value={form.default_tax_rate_id}
                onChange={(e) => updateField('default_tax_rate_id', e.target.value)}
                className="w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">None</option>
                {taxRates.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.name} ({tr.rate}%)
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </section>
  )
}
