import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listEvents, createEvent, updateEvent, deleteEvent } from '@/api/calendar'
import { schedulingApi } from '@/api/scheduling'
import { EVENT_TYPES } from '@/lib/constants'
import type { CalendarEvent, EventType, CalendarBooking } from '@/types/models'
import {
  Plus, ChevronLeft, ChevronRight, Clock, X, Phone, Video, MapPin, Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HOURS = Array.from({ length: 24 }, (_, i) => i)

type ViewMode = 'month' | 'week' | 'day'

interface CalendarItem {
  id: string
  title: string
  date: string
  startTime?: string
  endTime?: string
  type: 'event' | 'booking'
  color: string
  eventType?: string
  meetingType?: string
  guestName?: string
  guestEmail?: string
  status?: string
  isCompleted?: boolean
  raw: CalendarEvent | CalendarBooking
}

function getMeetingTypeIcon(type?: string) {
  if (type === 'phone') return <Phone className="h-3 w-3" />
  if (type === 'video') return <Video className="h-3 w-3" />
  if (type === 'in_person') return <MapPin className="h-3 w-3" />
  return null
}

export default function CalendarPage() {
  const queryClient = useQueryClient()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [viewMode, setViewMode] = useState<ViewMode>('month')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<CalendarItem | null>(null)
  const [newEvent, setNewEvent] = useState({ title: '', event_type: 'meeting' as EventType, description: '' })

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  // Calculate date range based on view mode
  const { dateFrom, dateTo } = useMemo(() => {
    if (viewMode === 'month') {
      const first = new Date(year, month, 1)
      const last = new Date(year, month + 1, 0)
      // Extend to cover full weeks
      const startPad = first.getDay()
      const start = new Date(year, month, 1 - startPad)
      const endPad = 6 - last.getDay()
      const end = new Date(year, month + 1, endPad)
      return { dateFrom: start.toISOString().split('T')[0], dateTo: end.toISOString().split('T')[0] }
    } else if (viewMode === 'week') {
      const dayOfWeek = currentDate.getDay()
      const start = new Date(year, month, currentDate.getDate() - dayOfWeek)
      const end = new Date(year, month, currentDate.getDate() + (6 - dayOfWeek))
      return { dateFrom: start.toISOString().split('T')[0], dateTo: end.toISOString().split('T')[0] }
    } else {
      const d = currentDate.toISOString().split('T')[0]
      return { dateFrom: d, dateTo: d }
    }
  }, [currentDate, viewMode, year, month])

  // Fetch both calendar events and bookings
  const { data: eventsData } = useQuery({
    queryKey: ['calendar-events', dateFrom, dateTo],
    queryFn: () => listEvents(dateFrom, dateTo),
  })

  const { data: bookingsData } = useQuery({
    queryKey: ['calendar-bookings-all', dateFrom, dateTo],
    queryFn: () => schedulingApi.listAllBookings(1, 200) as Promise<{ data: CalendarBooking[] }>,
  })

  const events: CalendarEvent[] = eventsData?.data ?? []
  const allBookings: CalendarBooking[] = (bookingsData?.data ?? []) as CalendarBooking[]

  // Filter bookings to date range
  const bookings = useMemo(() => {
    return allBookings.filter((b) => {
      const bDate = b.start_time.split('T')[0]
      return bDate >= dateFrom && bDate <= dateTo && b.status !== 'cancelled'
    })
  }, [allBookings, dateFrom, dateTo])

  // Merge events and bookings into unified items
  const items: CalendarItem[] = useMemo(() => {
    const result: CalendarItem[] = []
    events.forEach((evt) => {
      const typeInfo = EVENT_TYPES.find((t) => t.value === evt.event_type)
      result.push({
        id: evt.id,
        title: evt.title,
        date: evt.date,
        type: 'event',
        color: typeInfo?.color ?? '#6b7280',
        eventType: evt.event_type,
        isCompleted: evt.is_completed,
        raw: evt,
      })
    })
    bookings.forEach((b) => {
      result.push({
        id: b.id,
        title: `${b.guest_name}`,
        date: b.start_time.split('T')[0],
        startTime: b.start_time,
        endTime: b.end_time,
        type: 'booking',
        color: '#2563eb',
        meetingType: b.meeting_type,
        guestName: b.guest_name,
        guestEmail: b.guest_email,
        status: b.status,
        raw: b,
      })
    })
    return result
  }, [events, bookings])

  const itemsByDate = useMemo(() => {
    const map: Record<string, CalendarItem[]> = {}
    items.forEach((item) => {
      if (!map[item.date]) map[item.date] = []
      map[item.date].push(item)
    })
    return map
  }, [items])

  const createMutation = useMutation({
    mutationFn: (evt: { title: string; event_type: string; date: string; description?: string }) => createEvent(evt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
      setShowCreateForm(false)
      setNewEvent({ title: '', event_type: 'meeting', description: '' })
      toast.success('Event created')
    },
  })

  const toggleComplete = useMutation({
    mutationFn: (evt: CalendarEvent) => updateEvent(evt.id, { is_completed: !evt.is_completed } as any),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calendar-events'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteEvent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
      setSelectedItem(null)
      toast.success('Event deleted')
    },
  })

  // Navigation
  const navigate = useCallback((dir: number) => {
    setCurrentDate((prev) => {
      const d = new Date(prev)
      if (viewMode === 'month') d.setMonth(d.getMonth() + dir)
      else if (viewMode === 'week') d.setDate(d.getDate() + dir * 7)
      else d.setDate(d.getDate() + dir)
      return d
    })
  }, [viewMode])

  const goToday = () => setCurrentDate(new Date())

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newEvent.title.trim() || !selectedDate) return
    createMutation.mutate({
      title: newEvent.title.trim(),
      event_type: newEvent.event_type,
      date: selectedDate,
      description: newEvent.description || undefined,
    })
  }

  const today = new Date().toISOString().split('T')[0]

  const headerLabel = useMemo(() => {
    if (viewMode === 'month') return currentDate.toLocaleString('default', { month: 'long', year: 'numeric' })
    if (viewMode === 'week') {
      const dayOfWeek = currentDate.getDay()
      const start = new Date(year, month, currentDate.getDate() - dayOfWeek)
      const end = new Date(year, month, currentDate.getDate() + (6 - dayOfWeek))
      return `${start.toLocaleDateString('default', { month: 'short', day: 'numeric' })} – ${end.toLocaleDateString('default', { month: 'short', day: 'numeric', year: 'numeric' })}`
    }
    return currentDate.toLocaleDateString('default', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  }, [currentDate, viewMode, year, month])

  // Build month grid
  const monthDays = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const days: (number | null)[] = []
    for (let i = 0; i < firstDay; i++) days.push(null)
    for (let i = 1; i <= daysInMonth; i++) days.push(i)
    while (days.length % 7 !== 0) days.push(null)
    return days
  }, [year, month])

  // Week days
  const weekDays = useMemo(() => {
    const dayOfWeek = currentDate.getDay()
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(year, month, currentDate.getDate() - dayOfWeek + i)
      return d
    })
  }, [currentDate, year, month])

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="p-6 max-w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Calendar</h1>
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
            {(['month', 'week', 'day'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  'px-3 py-1 text-xs font-medium rounded-md transition',
                  viewMode === mode
                    ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
                )}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={goToday} className="px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800">Today</button>
          <button onClick={() => navigate(-1)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><ChevronLeft className="h-4 w-4" /></button>
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100 min-w-[180px] text-center">{headerLabel}</span>
          <button onClick={() => navigate(1)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><ChevronRight className="h-4 w-4" /></button>
          <button
            onClick={() => { setShowCreateForm(!showCreateForm); setSelectedDate(today) }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" /> New Event
          </button>
        </div>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <form onSubmit={handleCreateSubmit} className="bg-white dark:bg-gray-900 border rounded-lg p-4 mb-4 space-y-3">
          <div className="flex gap-3">
            <input
              type="text"
              value={newEvent.title}
              onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
              placeholder="Event title"
              className="flex-1 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              required
            />
            <select
              value={newEvent.event_type}
              onChange={(e) => setNewEvent({ ...newEvent, event_type: e.target.value as EventType })}
              className="px-3 py-2 text-sm border rounded-md dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            >
              {EVENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
              <option value="meeting">Meeting</option>
            </select>
            <input type="date" value={selectedDate ?? ''} onChange={(e) => setSelectedDate(e.target.value)} className="px-3 py-2 text-sm border rounded-md dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100" required />
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newEvent.description}
              onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
              placeholder="Description (optional)"
              className="flex-1 px-3 py-2 text-sm border rounded-md dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
            />
            <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">Create</button>
            <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 text-sm border rounded-md dark:border-gray-700 dark:text-gray-300">Cancel</button>
          </div>
        </form>
      )}

      {/* Calendar content */}
      <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
        {/* --- MONTH VIEW --- */}
        {viewMode === 'month' && (
          <>
            <div className="grid grid-cols-7 border-b">
              {DAYS.map((day) => (
                <div key={day} className="px-2 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 text-center">{day}</div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {monthDays.map((day, i) => {
                if (day === null) return <div key={i} className="min-h-24 border-b border-r bg-gray-50 dark:bg-gray-950" />
                const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                const dayItems = itemsByDate[dateKey] || []
                const isToday = dateKey === today

                return (
                  <div
                    key={i}
                    className={cn('min-h-24 border-b border-r p-1 cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-950/30', isToday && 'bg-blue-50 dark:bg-blue-950/20')}
                    onClick={() => { setSelectedDate(dateKey); setShowCreateForm(true) }}
                  >
                    <div className={cn('text-xs font-medium mb-1', isToday ? 'text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-gray-300')}>{day}</div>
                    <div className="space-y-0.5">
                      {dayItems.slice(0, 3).map((item) => (
                        <div
                          key={item.id}
                          className={cn('text-[10px] px-1 py-0.5 rounded truncate flex items-center gap-1', item.isCompleted && 'line-through opacity-50')}
                          style={{ backgroundColor: item.color + '20', color: item.color }}
                          onClick={(e) => { e.stopPropagation(); setSelectedItem(item) }}
                          title={item.title}
                        >
                          {item.type === 'booking' && getMeetingTypeIcon(item.meetingType)}
                          {item.type === 'booking' && item.startTime && <span>{formatTime(item.startTime)}</span>}
                          <span className="truncate">{item.title}</span>
                        </div>
                      ))}
                      {dayItems.length > 3 && <div className="text-[10px] text-gray-400 dark:text-gray-500">+{dayItems.length - 3} more</div>}
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {/* --- WEEK VIEW --- */}
        {viewMode === 'week' && (
          <>
            <div className="grid grid-cols-8 border-b">
              <div className="w-16 shrink-0" />
              {weekDays.map((d) => {
                const dateKey = d.toISOString().split('T')[0]
                const isToday = dateKey === today
                return (
                  <div key={dateKey} className={cn('py-2 text-center border-l', isToday && 'bg-blue-50 dark:bg-blue-950/20')}>
                    <div className="text-[10px] text-gray-500 dark:text-gray-400">{DAYS[d.getDay()]}</div>
                    <div className={cn('text-sm font-medium', isToday ? 'text-blue-600 dark:text-blue-400' : 'text-gray-900 dark:text-gray-100')}>{d.getDate()}</div>
                  </div>
                )
              })}
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              {HOURS.map((hour) => (
                <div key={hour} className="grid grid-cols-8 border-b min-h-[48px]">
                  <div className="w-16 shrink-0 text-[10px] text-gray-400 dark:text-gray-500 text-right pr-2 pt-1">
                    {hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`}
                  </div>
                  {weekDays.map((d) => {
                    const dateKey = d.toISOString().split('T')[0]
                    const dayItems = (itemsByDate[dateKey] || []).filter((item) => {
                      if (item.startTime) {
                        const h = new Date(item.startTime).getHours()
                        return h === hour
                      }
                      return hour === 9 && item.type === 'event' // Show all-day events at 9am
                    })
                    return (
                      <div
                        key={dateKey}
                        className="border-l relative min-h-[48px] hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer"
                        onClick={() => { setSelectedDate(dateKey); setShowCreateForm(true) }}
                      >
                        {dayItems.map((item) => (
                          <div
                            key={item.id}
                            className="text-[10px] px-1.5 py-0.5 rounded mx-0.5 mb-0.5 truncate flex items-center gap-1 cursor-pointer"
                            style={{ backgroundColor: item.color + '20', color: item.color }}
                            onClick={(e) => { e.stopPropagation(); setSelectedItem(item) }}
                          >
                            {item.type === 'booking' && getMeetingTypeIcon(item.meetingType)}
                            {item.startTime && <span>{formatTime(item.startTime)}</span>}
                            <span className="truncate">{item.title}</span>
                          </div>
                        ))}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          </>
        )}

        {/* --- DAY VIEW --- */}
        {viewMode === 'day' && (
          <div className="max-h-[600px] overflow-y-auto">
            {HOURS.map((hour) => {
              const dateKey = currentDate.toISOString().split('T')[0]
              const hourItems = (itemsByDate[dateKey] || []).filter((item) => {
                if (item.startTime) {
                  return new Date(item.startTime).getHours() === hour
                }
                return hour === 9 && item.type === 'event'
              })
              return (
                <div key={hour} className="flex border-b min-h-[56px]">
                  <div className="w-20 shrink-0 text-xs text-gray-400 dark:text-gray-500 text-right pr-3 pt-2">
                    {hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`}
                  </div>
                  <div className="flex-1 border-l px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer" onClick={() => { setSelectedDate(dateKey); setShowCreateForm(true) }}>
                    {hourItems.map((item) => (
                      <div
                        key={item.id}
                        className="text-xs px-2 py-1 rounded mb-1 flex items-center gap-2 cursor-pointer"
                        style={{ backgroundColor: item.color + '15', borderLeft: `3px solid ${item.color}` }}
                        onClick={(e) => { e.stopPropagation(); setSelectedItem(item) }}
                      >
                        {item.type === 'booking' && getMeetingTypeIcon(item.meetingType)}
                        <div className="min-w-0">
                          <div className="font-medium text-gray-900 dark:text-gray-100 truncate">{item.title}</div>
                          {item.startTime && item.endTime && (
                            <div className="text-gray-500 dark:text-gray-400 text-[10px]">
                              {formatTime(item.startTime)} – {formatTime(item.endTime)}
                            </div>
                          )}
                          {item.guestEmail && <div className="text-gray-400 dark:text-gray-500 text-[10px]">{item.guestEmail}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Item detail modal */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setSelectedItem(null)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  {selectedItem.type === 'booking' && getMeetingTypeIcon(selectedItem.meetingType)}
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{selectedItem.title}</h3>
                </div>
                <span
                  className="inline-block text-[10px] px-2 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: selectedItem.color + '20', color: selectedItem.color }}
                >
                  {selectedItem.type === 'booking' ? (selectedItem.meetingType?.replace('_', ' ') || 'booking') : selectedItem.eventType}
                </span>
              </div>
              <button onClick={() => setSelectedItem(null)} className="p-1 text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                <Clock className="h-4 w-4" />
                {selectedItem.startTime && selectedItem.endTime ? (
                  <span>{new Date(selectedItem.startTime).toLocaleDateString()} {formatTime(selectedItem.startTime)} – {formatTime(selectedItem.endTime)}</span>
                ) : (
                  <span>{selectedItem.date}</span>
                )}
              </div>

              {selectedItem.guestEmail && (
                <div className="text-gray-600 dark:text-gray-400">
                  <span className="font-medium text-gray-900 dark:text-gray-100">{selectedItem.guestName}</span> · {selectedItem.guestEmail}
                </div>
              )}

              {selectedItem.status && (
                <div className="text-gray-500 dark:text-gray-400">Status: <span className="capitalize font-medium">{selectedItem.status}</span></div>
              )}

              {selectedItem.type === 'booking' && (selectedItem.raw as CalendarBooking).meeting_location && (
                <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                  <MapPin className="h-4 w-4" />
                  {(selectedItem.raw as CalendarBooking).meeting_location}
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 mt-6 pt-4 border-t">
              {selectedItem.type === 'event' && (
                <>
                  <button
                    onClick={() => { toggleComplete.mutate(selectedItem.raw as CalendarEvent); setSelectedItem(null) }}
                    className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition"
                  >
                    {selectedItem.isCompleted ? 'Mark Incomplete' : 'Mark Complete'}
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(selectedItem.id)}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </button>
                </>
              )}
              <button
                onClick={() => setSelectedItem(null)}
                className="ml-auto px-3 py-1.5 text-sm border rounded-md dark:border-gray-700 dark:text-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
