/**
 * Public booking page — /book/:slug (no auth).
 *
 * Arivio-style slot picker (design ported from Arivio's
 * book/[username]/booking-widget.tsx): a 14-day grouped list of open
 * times → pick one → name/email form → confirmation. Runs against the
 * existing scheduling backend (GET /api/scheduling/public/{slug} with
 * days=14, POST /api/scheduling/public/{slug}/book).
 *
 * This page is also the target of the Calendar share hub's <iframe>
 * embed snippet, so it stays compact and self-contained — the backend
 * exempts /book/* from X-Frame-Options for exactly this reason.
 */
import { useState } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2, CheckCircle2, ArrowLeft, CalendarDays } from 'lucide-react'
import { schedulingApi } from '@/api/scheduling'

interface Slot {
  start: string
  end: string
}

interface SlotGroup {
  date: string
  slots: Slot[]
}

interface PublicCalendar {
  id: string
  name: string
  description: string | null
  duration_minutes: number
  timezone: string
  available_slots: Slot[]
  slot_groups: SlotGroup[]
}

const INPUT =
  'w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-[var(--brand-primary)]'

function Center({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-[300px] items-center justify-center p-6">{children}</div>
}

export default function PublicBookingPage() {
  const { slug } = useParams<{ slug: string }>()
  const [selected, setSelected] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const today = new Date().toISOString().split('T')[0]

  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-calendar', slug, today],
    queryFn: () =>
      schedulingApi.getPublicCalendar(slug!, today, 14) as Promise<{ data: PublicCalendar }>,
    enabled: !!slug,
  })

  const calendar = data?.data

  const bookMutation = useMutation({
    mutationFn: () =>
      schedulingApi.createBookingPublic(slug!, {
        guest_name: name.trim(),
        guest_email: email.trim().toLowerCase(),
        guest_phone: phone.trim() || null,
        guest_notes: notes.trim() || null,
        start_time: selected,
      }),
    onSuccess: () => setDone(true),
    onError: (err: unknown) => {
      setFormError(err instanceof Error ? err.message : 'Could not complete the booking.')
    },
  })

  const confirm = () => {
    if (!selected) return
    if (!name.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setFormError('Enter your name and a valid email')
      return
    }
    setFormError(null)
    bookMutation.mutate()
  }

  if (isLoading) {
    return (
      <Center>
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--brand-primary)' }} />
      </Center>
    )
  }

  if (isError || !calendar) {
    return (
      <Center>
        <div className="text-center">
          <CalendarDays className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500">This booking page doesn't exist or is no longer active.</p>
        </div>
      </Center>
    )
  }

  if (done) {
    return (
      <Center>
        <div className="text-center space-y-2">
          <CheckCircle2 className="mx-auto w-10 h-10 text-green-500" />
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">You're booked!</h2>
          <p className="text-sm text-gray-500">
            {selected &&
              new Date(selected).toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'short' })}
          </p>
          <p className="text-xs text-gray-400">
            A confirmation with a calendar invite is on its way to your email.
          </p>
        </div>
      </Center>
    )
  }

  const groups = (calendar.slot_groups ?? []).filter((g) => g.slots.length > 0)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="mx-auto max-w-md p-4">
        <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">{calendar.name}</h1>
        <p className="mt-0.5 text-xs text-gray-500">
          {calendar.duration_minutes} min · times shown in your local timezone
        </p>
        {calendar.description && (
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{calendar.description}</p>
        )}

        {!selected ? (
          <div className="mt-4 space-y-4">
            {groups.length === 0 ? (
              <p className="text-sm text-gray-500">No open times in the next 2 weeks. Check back soon.</p>
            ) : (
              groups.map((g) => (
                <div key={g.date}>
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    {new Date(g.date + 'T00:00:00').toLocaleDateString(undefined, {
                      weekday: 'long',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </p>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {g.slots.map((s) => (
                      <button
                        key={s.start}
                        onClick={() => setSelected(s.start)}
                        className="rounded-md border border-gray-300 dark:border-gray-600 px-2 py-2 text-xs font-medium text-gray-700 dark:text-gray-300 hover:border-[var(--brand-primary)] hover:text-[var(--brand-primary)] transition-colors"
                      >
                        {new Date(s.start).toLocaleTimeString(undefined, {
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <button
              onClick={() => setSelected(null)}
              className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Pick another time
            </button>
            <p
              className="rounded-md px-3 py-2 text-sm font-medium"
              style={{
                background: 'color-mix(in srgb, var(--brand-primary) 12%, transparent)',
                color: 'var(--brand-primary)',
              }}
            >
              {new Date(selected).toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'short' })}
            </p>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" className={INPUT} />
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className={INPUT} />
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (optional)" className={INPUT} />
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Anything to share? (optional)"
              className={INPUT}
            />
            {formError && <p className="text-xs text-red-500">{formError}</p>}
            <button
              onClick={confirm}
              disabled={bookMutation.isPending}
              className="w-full rounded-md px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 hover:opacity-90 transition-opacity"
              style={{ background: 'var(--brand-primary)' }}
            >
              {bookMutation.isPending ? 'Booking…' : 'Confirm booking'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
