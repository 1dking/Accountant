import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { schedulingApi } from '@/api/scheduling'
import type { SchedulingCalendar, CalendarBooking } from '@/types/models'
import {
  CalendarDays,
  Plus,
  Trash2,
  Clock,
  ExternalLink,
  XCircle,
  ArrowLeft,
} from 'lucide-react'

type View = 'calendars' | 'calendar-detail' | 'create'

export default function SchedulingPage() {
  const queryClient = useQueryClient()
  const [view, setView] = useState<View>('calendars')
  const [selectedCalId, setSelectedCalId] = useState<string | null>(null)
  const [bookingFilter, setBookingFilter] = useState<string>('')

  // Create form state
  const [name, setName] = useState('')
  const [calType, setCalType] = useState('personal')
  const [duration, setDuration] = useState(30)
  const [timezone, setTimezone] = useState('America/New_York')

  const { data: calendarsData } = useQuery({
    queryKey: ['scheduling-calendars'],
    queryFn: () => schedulingApi.listCalendars() as Promise<{ data: SchedulingCalendar[]; meta: { total_count: number } }>,
  })

  const { data: calDetail } = useQuery({
    queryKey: ['scheduling-calendar', selectedCalId],
    queryFn: () => schedulingApi.getCalendar(selectedCalId!) as Promise<{ data: SchedulingCalendar }>,
    enabled: !!selectedCalId,
  })

  const { data: bookingsData } = useQuery({
    queryKey: ['scheduling-bookings', selectedCalId, bookingFilter],
    queryFn: () => schedulingApi.listBookings(selectedCalId!, 1, 50, bookingFilter || undefined) as Promise<{ data: CalendarBooking[]; meta: { total_count: number } }>,
    enabled: !!selectedCalId && view === 'calendar-detail',
  })

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => schedulingApi.createCalendar(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendars'] })
      setView('calendars')
      setName('')
      toast.success('Calendar created')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => schedulingApi.deleteCalendar(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-calendars'] })
      setView('calendars')
      setSelectedCalId(null)
      toast.success('Calendar deleted')
    },
  })

  const cancelBookingMutation = useMutation({
    mutationFn: ({ calId, bookingId }: { calId: string; bookingId: string }) =>
      schedulingApi.cancelBooking(calId, bookingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduling-bookings'] })
      toast.success('Booking cancelled')
    },
  })

  const calendars = calendarsData?.data || []
  const detail = calDetail?.data
  const bookings = bookingsData?.data || []

  const openCalendar = (id: string) => {
    setSelectedCalId(id)
    setView('calendar-detail')
  }

  // --- Calendar List ---
  if (view === 'calendars') {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Scheduling</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Manage booking calendars and appointments</p>
          </div>
          <button
            onClick={() => setView('create')}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            <Plus className="h-4 w-4" />
            New Calendar
          </button>
        </div>

        {calendars.length === 0 ? (
          <div className="text-center py-20 text-gray-500 dark:text-gray-400">
            <CalendarDays className="h-12 w-12 mx-auto mb-4 opacity-40" />
            <p>No calendars yet. Create your first booking calendar.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {calendars.map((cal) => (
              <div
                key={cal.id}
                className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition cursor-pointer"
                onClick={() => openCalendar(cal.id)}
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                    <CalendarDays className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100">{cal.name}</h3>
                    <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{cal.duration_minutes}min</span>
                      <span className="capitalize">{cal.calendar_type}</span>
                      <span>/{cal.slug}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {cal.is_active ? (
                    <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Active</span>
                  ) : (
                    <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">Inactive</span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(cal.id) }}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // --- Create Calendar ---
  if (view === 'create') {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <button onClick={() => setView('calendars')} className="flex items-center gap-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-6">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-6">Create Booking Calendar</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Calendar Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              placeholder="e.g. Consultation Call"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
              <select
                value={calType}
                onChange={(e) => setCalType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
                <option value="personal">Personal</option>
                <option value="team">Team</option>
                <option value="round_robin">Round Robin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Duration (min)</label>
              <input
                type="number"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Timezone</label>
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            />
          </div>
          <button
            onClick={() => createMutation.mutate({ name, calendar_type: calType, duration_minutes: duration, timezone })}
            disabled={!name.trim() || createMutation.isPending}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Calendar'}
          </button>
        </div>
      </div>
    )
  }

  // --- Calendar Detail / Bookings ---
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <button onClick={() => { setView('calendars'); setSelectedCalId(null) }} className="flex items-center gap-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to calendars
      </button>

      {detail && (
        <>
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{detail.name}</h2>
              <a
                href={`/book/${detail.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                <ExternalLink className="h-4 w-4" />
                Public booking link
              </a>
            </div>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div><span className="text-gray-500 dark:text-gray-400">Type:</span> <span className="capitalize text-gray-900 dark:text-gray-100">{detail.calendar_type}</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Duration:</span> <span className="text-gray-900 dark:text-gray-100">{detail.duration_minutes}min</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Buffer:</span> <span className="text-gray-900 dark:text-gray-100">{detail.buffer_minutes}min</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">Timezone:</span> <span className="text-gray-900 dark:text-gray-100">{detail.timezone}</span></div>
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Bookings</h3>
            <div className="flex items-center gap-2">
              {['', 'confirmed', 'pending', 'cancelled'].map((f) => (
                <button
                  key={f}
                  onClick={() => setBookingFilter(f)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition ${
                    bookingFilter === f
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  {f || 'All'}
                </button>
              ))}
            </div>
          </div>

          {bookings.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              No bookings found.
            </div>
          ) : (
            <div className="space-y-3">
              {bookings.map((b) => (
                <div key={b.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-gray-100">{b.guest_name}</span>
                      <span className="text-sm text-gray-500 dark:text-gray-400">{b.guest_email}</span>
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {new Date(b.start_time).toLocaleDateString()} {new Date(b.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - {new Date(b.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      b.status === 'confirmed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                      b.status === 'cancelled' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                      'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    }`}>
                      {b.status}
                    </span>
                    {b.status !== 'cancelled' && (
                      <button
                        onClick={() => selectedCalId && cancelBookingMutation.mutate({ calId: selectedCalId, bookingId: b.id })}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition"
                        title="Cancel booking"
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
