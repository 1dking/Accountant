/**
 * Bookings — /bookings (authenticated).
 *
 * Arivio-style bookings list: upcoming/past tabs, guest info, status
 * chips, cancel action. Runs on the existing scheduling backend
 * (GET /api/scheduling/bookings/all + POST .../bookings/{id}/cancel).
 * Part of the Phase-2 split of the old SchedulingPage into
 * Bookings / Availability / Calendar-share-hub.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Mail, Phone as PhoneIcon, XCircle } from 'lucide-react'
import { schedulingApi } from '@/api/scheduling'
import { toast } from 'sonner'

interface BookingItem {
  id: string
  calendar_id: string
  guest_name: string
  guest_email: string
  guest_phone?: string | null
  start_time: string
  end_time: string
  status: string
  meeting_type: string | null
  created_at: string
}

const STATUS_STYLES: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  cancelled: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  no_show: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400',
}

export default function BookingsPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'upcoming' | 'past'>('upcoming')

  const { data, isLoading } = useQuery({
    queryKey: ['bookings-all'],
    queryFn: () =>
      schedulingApi.listAllBookings(1, 100) as Promise<{ data: BookingItem[] }>,
  })

  const cancelMutation = useMutation({
    mutationFn: ({ calendarId, bookingId }: { calendarId: string; bookingId: string }) =>
      schedulingApi.cancelBooking(calendarId, bookingId),
    onSuccess: () => {
      toast.success('Booking cancelled')
      queryClient.invalidateQueries({ queryKey: ['bookings-all'] })
    },
    onError: () => toast.error('Failed to cancel booking'),
  })

  // Snapshotted once per mount — a stable "now" keeps the upcoming/past
  // split from flickering across re-renders (and satisfies purity rules).
  const [now] = useState(() => Date.now())
  const bookings = (data?.data ?? []).filter((b) => {
    const isPast = new Date(b.start_time).getTime() < now
    return tab === 'upcoming' ? !isPast : isPast
  })

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Bookings</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Meetings your clients booked through your public calendar.
        </p>
      </div>

      <div className="flex gap-1 mb-4 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
        {(['upcoming', 'past'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm rounded-md capitalize transition-colors ${
              tab === t
                ? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-gray-400 text-sm py-8">Loading bookings…</p>
      ) : bookings.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border rounded-lg">
          <CalendarDays className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            No {tab} bookings.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {bookings.map((b) => (
            <div
              key={b.id}
              className="bg-white dark:bg-gray-900 border rounded-lg p-4 flex items-start justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900 dark:text-gray-100">{b.guest_name}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                      STATUS_STYLES[b.status] ?? STATUS_STYLES.pending
                    }`}
                  >
                    {b.status.replace('_', ' ')}
                  </span>
                  {b.meeting_type && (
                    <span className="text-xs text-gray-400 capitalize">{b.meeting_type.replace('_', ' ')}</span>
                  )}
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {new Date(b.start_time).toLocaleString(undefined, {
                    dateStyle: 'full',
                    timeStyle: 'short',
                  })}
                </p>
                <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
                  <span className="inline-flex items-center gap-1">
                    <Mail className="w-3 h-3" /> {b.guest_email}
                  </span>
                  {b.guest_phone && (
                    <span className="inline-flex items-center gap-1">
                      <PhoneIcon className="w-3 h-3" /> {b.guest_phone}
                    </span>
                  )}
                </div>
              </div>
              {tab === 'upcoming' && b.status !== 'cancelled' && (
                <button
                  onClick={() => {
                    if (confirm(`Cancel the booking with ${b.guest_name}?`)) {
                      cancelMutation.mutate({ calendarId: b.calendar_id, bookingId: b.id })
                    }
                  }}
                  disabled={cancelMutation.isPending}
                  className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50 shrink-0"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Cancel
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
