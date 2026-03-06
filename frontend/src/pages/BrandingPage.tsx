import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { brandingApi } from '@/api/branding'
import type { BrandingSettings } from '@/types/models'
import { Palette, Save } from 'lucide-react'

export default function BrandingPage() {
  const queryClient = useQueryClient()

  const { data: brandingData, isLoading } = useQuery({
    queryKey: ['branding'],
    queryFn: () => brandingApi.get() as Promise<{ data: BrandingSettings }>,
  })

  const [form, setForm] = useState({
    logo_url: '',
    logo_dark_url: '',
    favicon_url: '',
    primary_color: '#2563eb',
    secondary_color: '#64748b',
    accent_color: '#f59e0b',
    font_heading: 'Inter',
    font_body: 'Inter',
    border_radius: '8px',
    custom_css: '',
    email_header_html: '',
    email_footer_html: '',
    portal_welcome_message: '',
    booking_page_header: '',
    org_slug: '',
  })

  useEffect(() => {
    if (brandingData?.data) {
      const b = brandingData.data
      setForm({
        logo_url: b.logo_url || '',
        logo_dark_url: b.logo_dark_url || '',
        favicon_url: b.favicon_url || '',
        primary_color: b.primary_color || '#2563eb',
        secondary_color: b.secondary_color || '#64748b',
        accent_color: b.accent_color || '#f59e0b',
        font_heading: b.font_heading || 'Inter',
        font_body: b.font_body || 'Inter',
        border_radius: b.border_radius || '8px',
        custom_css: b.custom_css || '',
        email_header_html: b.email_header_html || '',
        email_footer_html: b.email_footer_html || '',
        portal_welcome_message: b.portal_welcome_message || '',
        booking_page_header: b.booking_page_header || '',
        org_slug: b.org_slug || '',
      })
    }
  }, [brandingData])

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => brandingApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['branding'] })
      toast.success('Branding updated')
    },
  })

  const handleSave = () => {
    updateMutation.mutate(form)
  }

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  if (isLoading) {
    return <div className="p-6 text-gray-500">Loading branding settings...</div>
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Palette className="h-6 w-6" />
            Branding
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Configure your brand identity across all touchpoints</p>
        </div>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
        >
          <Save className="h-4 w-4" />
          {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <div className="space-y-8">
        {/* Organization */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Organization</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Organization Slug</label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">/p/</span>
              <input
                value={form.org_slug}
                onChange={(e) => updateField('org_slug', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                placeholder="my-company"
              />
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Used for public page URLs: /p/my-company/page-slug</p>
          </div>
        </section>

        {/* Logo & Favicon */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Logo & Favicon</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Logo URL</label>
              <input
                value={form.logo_url}
                onChange={(e) => updateField('logo_url', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                placeholder="https://..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Dark Mode Logo URL</label>
              <input
                value={form.logo_dark_url}
                onChange={(e) => updateField('logo_dark_url', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                placeholder="https://..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Favicon URL</label>
              <input
                value={form.favicon_url}
                onChange={(e) => updateField('favicon_url', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                placeholder="https://..."
              />
            </div>
          </div>
          {form.logo_url && (
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
              <p className="text-xs text-gray-500 mb-2">Preview:</p>
              <img src={form.logo_url} alt="Logo preview" className="max-h-12" />
            </div>
          )}
        </section>

        {/* Colors */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Colors</h2>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Primary', field: 'primary_color' },
              { label: 'Secondary', field: 'secondary_color' },
              { label: 'Accent', field: 'accent_color' },
            ].map(({ label, field }) => (
              <div key={field}>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={form[field as keyof typeof form]}
                    onChange={(e) => updateField(field, e.target.value)}
                    className="h-10 w-10 rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
                  />
                  <input
                    value={form[field as keyof typeof form]}
                    onChange={(e) => updateField(field, e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm"
                  />
                </div>
              </div>
            ))}
          </div>
          {/* Color preview */}
          <div className="mt-4 flex gap-2">
            <div className="h-8 flex-1 rounded-lg" style={{ background: form.primary_color }} />
            <div className="h-8 flex-1 rounded-lg" style={{ background: form.secondary_color }} />
            <div className="h-8 flex-1 rounded-lg" style={{ background: form.accent_color }} />
          </div>
        </section>

        {/* Typography */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Typography</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Heading Font</label>
              <input
                value={form.font_heading}
                onChange={(e) => updateField('font_heading', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Body Font</label>
              <input
                value={form.font_body}
                onChange={(e) => updateField('font_body', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Border Radius</label>
              <input
                value={form.border_radius}
                onChange={(e) => updateField('border_radius', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
              />
            </div>
          </div>
        </section>

        {/* Portal & Booking */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Portal & Booking</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Portal Welcome Message</label>
              <textarea
                value={form.portal_welcome_message}
                onChange={(e) => updateField('portal_welcome_message', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
                rows={3}
                placeholder="Welcome to your client portal..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Booking Page Header HTML</label>
              <textarea
                value={form.booking_page_header}
                onChange={(e) => updateField('booking_page_header', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm"
                rows={3}
                placeholder="<h2>Book a meeting with us</h2>"
              />
            </div>
          </div>
        </section>

        {/* Email Branding */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Email Branding</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Header HTML</label>
              <textarea
                value={form.email_header_html}
                onChange={(e) => updateField('email_header_html', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm"
                rows={4}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email Footer HTML</label>
              <textarea
                value={form.email_footer_html}
                onChange={(e) => updateField('email_footer_html', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm"
                rows={4}
              />
            </div>
          </div>
        </section>

        {/* Custom CSS */}
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Custom CSS</h2>
          <textarea
            value={form.custom_css}
            onChange={(e) => updateField('custom_css', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm"
            rows={8}
            placeholder="/* Custom styles applied to portal, booking pages, etc. */"
          />
        </section>
      </div>
    </div>
  )
}
