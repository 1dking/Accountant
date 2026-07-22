/**
 * Calendar — /calendar (authenticated).
 *
 * Arivio-style share hub (design ported from Arivio's dashboard
 * calendar-client.tsx): your public booking link, a copy-paste iframe
 * embed snippet, a QR code, a live preview, and a shortcut to the
 * Availability editor. Replaced the old month/week/day event grid per
 * the Phase-2 decision — the internal CalendarEvent API is untouched
 * (the Dashboard's upcoming list still reads it), so a grid view can
 * return later without backend work.
 */
import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { CalendarDays, Copy, ExternalLink } from 'lucide-react'
import { schedulingApi } from '@/api/scheduling'
import { toast } from 'sonner'

interface CalendarItem {
  id: string
  name: string
  slug: string
  calendar_type: string
  is_active: boolean
}

export default function CalendarPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['scheduling-calendars'],
    queryFn: () => schedulingApi.listCalendars() as Promise<{ data: CalendarItem[] }>,
  })
  const calendars = (data?.data ?? []).filter((c) => c.is_active)
  const active = calendars.find((c) => c.id === selectedId) ?? calendars[0] ?? null

  const createMutation = useMutation({
    mutationFn: () => schedulingApi.createCalendar({ name: 'Meetings' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendars'] })
      toast.success('Booking calendar created')
    },
  })

  if (isLoading) {
    return <div className="p-6 text-gray-500">Loading calendar…</div>
  }

  if (!active) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-4">Calendar</h1>
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <CalendarDays className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Create a booking calendar to get your shareable link.
          </p>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
            style={{ background: 'var(--brand-primary)' }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create booking calendar'}
          </button>
        </div>
      </div>
    )
  }

  const bookUrl = `${window.location.origin}/book/${active.slug}`
  const embed = `<iframe src="${bookUrl}" width="100%" height="720" frameborder="0" style="border:0;border-radius:12px;max-width:480px"></iframe>`

  const copy = (text: string, label: string) => {
    navigator.clipboard?.writeText(text)
    toast.success(`${label} copied`)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Calendar</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Your booking calendar as a standalone page you can share or embed anywhere.
            </p>
          </div>

          {calendars.length > 1 && (
            <select
              value={active.id}
              onChange={(e) => setSelectedId(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
            >
              {calendars.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}

          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              Public link
            </span>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={bookUrl}
                className="flex-1 rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-950 px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-100"
              />
              <button
                onClick={() => copy(bookUrl, 'Link')}
                className="p-2 border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
                title="Copy link"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
              <a
                href={bookUrl}
                target="_blank"
                rel="noreferrer"
                className="p-2 border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
                title="Open in new tab"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </section>

          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              Embed on your website
            </span>
            <textarea
              readOnly
              value={embed}
              rows={3}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-950 px-3 py-2 text-xs font-mono text-gray-900 dark:text-gray-100"
            />
            <button
              onClick={() => copy(embed, 'Embed code')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <Copy className="w-3.5 h-3.5" /> Copy embed code
            </button>
          </section>

          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              QR code
            </span>
            <div className="bg-white p-3 rounded-lg w-fit border">
              <QRCodeSVG value={bookUrl} size={128} />
            </div>
            <p className="text-xs text-gray-500">Scan to open your booking page.</p>
          </section>

          <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 flex items-center gap-3">
            <CalendarDays className="w-5 h-5 shrink-0" style={{ color: 'var(--brand-primary)' }} />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                Availability & meeting preferences
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Set your weekly hours, duration, buffer, and timezone.
              </p>
            </div>
            <Link
              to="/availability"
              className="px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Configure
            </Link>
          </section>
        </div>

        <div className="lg:sticky lg:top-4 h-fit">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-gray-400">Preview</p>
          <div className="mx-auto w-full max-w-[320px] rounded-[2rem] border-4 border-gray-800 dark:border-gray-200 overflow-hidden bg-white">
            <iframe src={bookUrl} title="Booking page preview" className="w-full" style={{ height: 560, border: 0 }} />
          </div>
        </div>
      </div>
    </div>
  )
}
