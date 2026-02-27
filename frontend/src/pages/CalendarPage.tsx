import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listEvents, createEvent, updateEvent } from '@/api/calendar'
import { EVENT_TYPES } from '@/lib/constants'
import type { CalendarEvent, EventType } from '@/types/models'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function CalendarPage() {
  const queryClient = useQueryClient()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [newEvent, setNewEvent] = useState({ title: '', event_type: 'deadline' as EventType, description: '' })

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  const dateFrom = new Date(year, month, 1).toISOString().split('T')[0]
  const dateTo = new Date(year, month + 1, 0).toISOString().split('T')[0]

  const { data } = useQuery({
    queryKey: ['calendar-events', dateFrom, dateTo],
    queryFn: () => listEvents(dateFrom, dateTo),
  })

  const events: CalendarEvent[] = data?.data ?? []

  const createMutation = useMutation({
    mutationFn: (evt: { title: string; event_type: string; date: string; description?: string }) =>
      createEvent(evt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
      setShowCreateForm(false)
      setNewEvent({ title: '', event_type: 'deadline', description: '' })
    },
  })

  const toggleComplete = useMutation({
    mutationFn: (evt: CalendarEvent) => updateEvent(evt.id, { is_completed: !evt.is_completed } as any),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calendar-events'] }),
  })

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const days: (number | null)[] = []

    for (let i = 0; i < firstDay; i++) days.push(null)
    for (let i = 1; i <= daysInMonth; i++) days.push(i)
    while (days.length % 7 !== 0) days.push(null)

    return days
  }, [year, month])

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    events.forEach((evt) => {
      const dateKey = evt.date
      if (!map[dateKey]) map[dateKey] = []
      map[dateKey].push(evt)
    })
    return map
  }, [events])

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1))
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1))

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

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Calendar</h1>
        <button
          onClick={() => {
            setShowCreateForm(!showCreateForm)
            setSelectedDate(today)
          }}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          New Event
        </button>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <form onSubmit={handleCreateSubmit} className="bg-white border rounded-lg p-4 mb-6 space-y-3">
          <div className="flex gap-3">
            <input
              type="text"
              value={newEvent.title}
              onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
              placeholder="Event title"
              className="flex-1 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <select
              value={newEvent.event_type}
              onChange={(e) => setNewEvent({ ...newEvent, event_type: e.target.value as EventType })}
              className="px-3 py-2 text-sm border rounded-md bg-white"
            >
              {EVENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <input
              type="date"
              value={selectedDate ?? ''}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-3 py-2 text-sm border rounded-md"
              required
            />
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newEvent.description}
              onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
              placeholder="Description (optional)"
              className="flex-1 px-3 py-2 text-sm border rounded-md"
            />
            <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
              Create
            </button>
            <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 text-sm border rounded-md">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Calendar header */}
      <div className="bg-white border rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <button onClick={prevMonth} className="px-3 py-1 text-sm hover:bg-gray-100 rounded">{'\u2190'}</button>
          <h2 className="text-lg font-medium text-gray-900">
            {currentDate.toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h2>
          <button onClick={nextMonth} className="px-3 py-1 text-sm hover:bg-gray-100 rounded">{'\u2192'}</button>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 border-b">
          {DAYS.map((day) => (
            <div key={day} className="px-2 py-2 text-xs font-medium text-gray-500 text-center">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid grid-cols-7">
          {calendarDays.map((day, i) => {
            if (day === null) return <div key={i} className="min-h-24 border-b border-r bg-gray-50" />
            const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
            const dayEvents = eventsByDate[dateKey] || []
            const isToday = dateKey === today

            return (
              <div
                key={i}
                className={`min-h-24 border-b border-r p-1 cursor-pointer hover:bg-blue-50 ${
                  isToday ? 'bg-blue-50' : ''
                }`}
                onClick={() => {
                  setSelectedDate(dateKey)
                  setShowCreateForm(true)
                }}
              >
                <div className={`text-xs font-medium mb-1 ${isToday ? 'text-blue-600' : 'text-gray-700'}`}>
                  {day}
                </div>
                <div className="space-y-0.5">
                  {dayEvents.slice(0, 3).map((evt) => {
                    const typeInfo = EVENT_TYPES.find((t) => t.value === evt.event_type)
                    return (
                      <div
                        key={evt.id}
                        className={`text-[10px] px-1 py-0.5 rounded truncate ${
                          evt.is_completed ? 'line-through opacity-50' : ''
                        }`}
                        style={{ backgroundColor: (typeInfo?.color ?? '#6b7280') + '20', color: typeInfo?.color }}
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleComplete.mutate(evt)
                        }}
                        title={evt.title}
                      >
                        {evt.title}
                      </div>
                    )
                  })}
                  {dayEvents.length > 3 && (
                    <div className="text-[10px] text-gray-400">+{dayEvents.length - 3} more</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
