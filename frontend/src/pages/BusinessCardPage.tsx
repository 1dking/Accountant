/**
 * Business Card editor — /business-card (authenticated).
 *
 * Arivio-style customizer: template picker, identity fields, palette,
 * booking-calendar link, publish toggle, live preview (renders the
 * real template components against a client-side approximation of the
 * server-resolved public payload), and a share panel (URL + QR).
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { Copy, ExternalLink, Save, Upload } from 'lucide-react'
import { cardsApi, type BusinessCard, type PublicCard } from '@/api/cards'
import { schedulingApi } from '@/api/scheduling'
import ClassicCard from '@/components/cards/templates/ClassicCard'
import {
  CARD_TEMPLATES as TEMPLATES,
  CARD_TEMPLATE_OPTIONS,
} from '@/components/cards/templates'
import { toast } from 'sonner'

const INPUT =
  'w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100'

interface SchedCal {
  id: string
  name: string
  slug: string
  is_active: boolean
}

type Draft = Partial<BusinessCard>

export default function BusinessCardPage() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>({})
  const [syncedId, setSyncedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['my-card'],
    queryFn: () => cardsApi.getMyCard(),
  })
  const card = data?.data

  // Render-time sync: seed the draft once per loaded card.
  if (card && card.id !== syncedId) {
    setSyncedId(card.id)
    setDraft(card)
  }

  const { data: calsData } = useQuery({
    queryKey: ['scheduling-calendars'],
    queryFn: () => schedulingApi.listCalendars() as Promise<{ data: SchedCal[] }>,
  })
  const calendars = (calsData?.data ?? []).filter((c) => c.is_active)

  const { data: analyticsData } = useQuery({
    queryKey: ['my-card-analytics'],
    queryFn: () => cardsApi.getMyCardAnalytics(),
  })
  const analytics = analyticsData?.data

  const saveMutation = useMutation({
    mutationFn: (payload: Draft) => cardsApi.updateMyCard(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-card'] })
      toast.success('Card saved')
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Failed to save card')
    },
  })

  const avatarMutation = useMutation({
    mutationFn: (file: File) => cardsApi.uploadAvatar(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-card'] })
      toast.success('Photo uploaded')
    },
    onError: () => toast.error('Failed to upload photo'),
  })

  if (isLoading || !card) {
    return <div className="p-6 text-gray-500">Loading your card…</div>
  }

  const set = (field: keyof BusinessCard, value: unknown) =>
    setDraft((d) => ({ ...d, [field]: value }))

  const cardUrl = `${window.location.origin}/c/${card.slug}`
  const linkedCal = calendars.find((c) => c.id === draft.scheduling_calendar_id)

  // Client-side approximation of the server-resolved public payload for
  // the live preview (the server applies org-branding fallbacks; here
  // we fall back to sensible defaults).
  const preview: PublicCard = {
    slug: card.slug,
    template: (draft.template as PublicCard['template']) ?? 'classic',
    display_name: draft.display_name || 'Your Name',
    job_title: draft.job_title ?? null,
    company_name: draft.company_name ?? null,
    tagline: draft.tagline ?? null,
    email: draft.email ?? null,
    phone: draft.phone ?? null,
    website: draft.website ?? null,
    social_links: {},
    avatar_url: card.avatar_storage_path ? `/api/cards/public/${card.slug}/avatar` : null,
    logo_url: null,
    bg_color: draft.bg_color || '#ffffff',
    text_color: draft.text_color || '#111827',
    accent_color: draft.accent_color || '#2563eb',
    button_color: draft.button_color || '#2563eb',
    button_text_color: draft.button_text_color || '#ffffff',
    font: draft.font || 'Inter',
    booking_url: draft.show_booking && linkedCal ? `/book/${linkedCal.slug}` : null,
    wallet_available: { apple: false, google: false },
  }
  const PreviewTemplate = TEMPLATES[preview.template] ?? ClassicCard

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Business Card</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Your shareable digital card — one link, one QR code, one tap to save your contact.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={!!draft.is_published}
              onChange={(e) => set('is_published', e.target.checked)}
            />
            Published
          </label>
          <button
            onClick={() => saveMutation.mutate(draft)}
            disabled={saveMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
            style={{ background: 'var(--brand-primary)' }}
          >
            <Save className="w-4 h-4" />
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          {/* Template — live mini-previews rendered in the user's own palette */}
          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Template</h2>
            <div className="grid grid-cols-3 gap-3">
              {CARD_TEMPLATE_OPTIONS.map(({ id, label }) => {
                const Thumb = TEMPLATES[id]
                const selected = (draft.template ?? 'classic') === id
                return (
                  <button
                    key={id}
                    onClick={() => set('template', id)}
                    className={`group text-left rounded-lg border-2 overflow-hidden transition-all ${
                      selected
                        ? 'border-[var(--brand-primary)] ring-2 ring-[var(--brand-primary)]/30'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500'
                    }`}
                  >
                    <div className="relative h-40 overflow-hidden bg-gray-100 dark:bg-gray-800 pointer-events-none select-none">
                      <div
                        className="absolute top-0 left-1/2 w-[320px] h-[460px] origin-top-left [&>div]:!min-h-full"
                        style={{ transform: 'scale(0.35)', marginLeft: '-56px' }}
                        aria-hidden
                      >
                        <Thumb
                          card={{ ...preview, template: id }}
                          cardUrl={cardUrl}
                          onSaveContact={() => {}}
                          onShowQr={() => {}}
                        />
                      </div>
                    </div>
                    <p
                      className={`px-2 py-1.5 text-xs font-medium text-center ${
                        selected
                          ? 'text-[var(--brand-primary)]'
                          : 'text-gray-600 dark:text-gray-400'
                      }`}
                    >
                      {label}
                    </p>
                  </button>
                )
              })}
            </div>
          </section>

          {/* Identity */}
          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Identity</h2>
            <div className="grid grid-cols-2 gap-3">
              <input value={draft.display_name ?? ''} onChange={(e) => set('display_name', e.target.value)} placeholder="Full name" className={INPUT} />
              <input value={draft.job_title ?? ''} onChange={(e) => set('job_title', e.target.value)} placeholder="Job title" className={INPUT} />
              <input value={draft.company_name ?? ''} onChange={(e) => set('company_name', e.target.value)} placeholder="Company" className={INPUT} />
              <input value={draft.email ?? ''} onChange={(e) => set('email', e.target.value)} placeholder="Email" className={INPUT} />
              <input value={draft.phone ?? ''} onChange={(e) => set('phone', e.target.value)} placeholder="Phone" className={INPUT} />
              <input value={draft.website ?? ''} onChange={(e) => set('website', e.target.value)} placeholder="Website (https://…)" className={INPUT} />
            </div>
            <textarea value={draft.tagline ?? ''} onChange={(e) => set('tagline', e.target.value)} rows={2} placeholder="Short tagline or bio" className={INPUT} />
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg cursor-pointer text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
                <Upload className="w-4 h-4" />
                {avatarMutation.isPending ? 'Uploading…' : 'Upload photo'}
                <input
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) avatarMutation.mutate(f)
                  }}
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={!!draft.show_org_logo}
                  onChange={(e) => set('show_org_logo', e.target.checked)}
                />
                Show company logo
              </label>
            </div>
          </section>

          {/* Palette */}
          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Colors & font</h2>
            <div className="grid grid-cols-3 gap-3">
              {(
                [
                  ['bg_color', 'Background', '#ffffff'],
                  ['text_color', 'Text', '#111827'],
                  ['accent_color', 'Accent', '#2563eb'],
                  ['button_color', 'Button', '#2563eb'],
                  ['button_text_color', 'Button text', '#ffffff'],
                ] as const
              ).map(([field, label, fallback]) => (
                <div key={field}>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</label>
                  <input
                    type="color"
                    value={(draft[field] as string) || fallback}
                    onChange={(e) => set(field, e.target.value)}
                    className="h-9 w-full rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Font</label>
                <input
                  value={draft.font ?? ''}
                  onChange={(e) => set('font', e.target.value || null)}
                  placeholder="Inter"
                  className={INPUT}
                />
              </div>
            </div>
          </section>

          {/* Booking */}
          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Booking</h2>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={!!draft.show_booking}
                onChange={(e) => set('show_booking', e.target.checked)}
              />
              Show a "Book a meeting" button
            </label>
            {draft.show_booking && (
              <select
                value={draft.scheduling_calendar_id ?? ''}
                onChange={(e) => set('scheduling_calendar_id', e.target.value || null)}
                className={INPUT}
              >
                <option value="">Select a booking calendar…</option>
                {calendars.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (/book/{c.slug})
                  </option>
                ))}
              </select>
            )}
          </section>

          {/* Analytics */}
          {analytics && (
            <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Analytics</h2>
              <div className="grid grid-cols-3 gap-3">
                {(
                  [
                    ['Views', analytics.total_views],
                    ['Unique visitors', analytics.unique_visitors],
                    ['Contacts saved', analytics.total_vcard_downloads],
                  ] as const
                ).map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-4 text-center"
                  >
                    <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{label}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Share */}
          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Share</h2>
            {card.is_published ? (
              <>
                <div className="flex items-center gap-2">
                  <input readOnly value={cardUrl} className={`${INPUT} font-mono`} />
                  <button
                    onClick={() => {
                      navigator.clipboard?.writeText(cardUrl)
                      toast.success('Link copied')
                    }}
                    className="p-2 border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                  <a href={cardUrl} target="_blank" rel="noreferrer" className="p-2 border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
                <div className="bg-white p-2 rounded-lg border w-fit">
                  <QRCodeSVG value={cardUrl} size={112} />
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-500">Publish your card to get its shareable link and QR code.</p>
            )}
          </section>
        </div>

        {/* Live preview */}
        <div className="lg:sticky lg:top-4 h-fit">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-gray-400">Preview</p>
          <div className="mx-auto w-full max-w-[320px] rounded-[2rem] border-4 border-gray-800 dark:border-gray-200 overflow-hidden bg-white">
            <div className="h-[560px] overflow-y-auto [&>div]:min-h-full">
              <PreviewTemplate
                card={preview}
                cardUrl={cardUrl}
                onSaveContact={() => toast('Visitors get a .vcf contact download here')}
                onShowQr={() => toast('Visitors get the QR share overlay here')}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
