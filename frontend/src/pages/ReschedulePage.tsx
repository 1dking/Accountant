import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import { schedulingApi } from '@/api/scheduling'
import { CalendarDays, Clock, ArrowRight, Check, AlertCircle } from 'lucide-react'

export default function ReschedulePage() {
  const { token } = useParams<{ token: string }>()
  const [booking, setBooking] = useState<any>(null)
  const [calendarName, setCalendarName] = useState('')
  const [durationMinutes, setDurationMinutes] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [slots, setSlots] = useState<any[]>([])
  const [selectedSlot, setSelectedSlot] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [loadingSlots, setLoadingSlots] = useState(false)

  useEffect(() => {
    if (!token) return
    schedulingApi.getRescheduleInfo(token)
      .then((res: any) => {
        const data = res.data?.data || res.data
        setBooking(data.booking)
        setCalendarName(data.calendar_name)
        setDurationMinutes(data.duration_minutes || 30)
      })
      .catch(() => setError('This reschedule link is invalid or has expired.'))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    if (!selectedDate || !booking) return
    setLoadingSlots(true)
    // Use the public calendar endpoint to get slots
    const calId = booking.calendar_id
    schedulingApi.getSlots(calId, selectedDate)
      .then((res: any) => {
        const data = res.data?.data || res.data
        setSlots(Array.isArray(data) ? data : [])
      })
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false))
  }, [selectedDate, booking])

  const handleReschedule = async () => {
    if (!token || !selectedSlot) return
    setSubmitting(true)
    try {
      await schedulingApi.rescheduleBooking(token, selectedSlot)
      setSuccess(true)
    } catch {
      setError('Failed to reschedule. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-pulse text-gray-500">Loading...</div>
      </div>
    )
  }

  if (error && !booking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 mb-2">Link Invalid</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Rescheduled!</h1>
          <p className="text-gray-600">
            Your appointment has been rescheduled to{' '}
            <strong>{new Date(selectedSlot).toLocaleString()}</strong>.
          </p>
          <p className="text-sm text-gray-500 mt-4">You will receive a confirmation email shortly.</p>
        </div>
      </div>
    )
  }

  // Generate dates for next 30 days
  const dates: string[] = []
  const today = new Date()
  for (let i = 0; i < 30; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() + i)
    dates.push(d.toISOString().split('T')[0])
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-lg mx-auto">
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          {/* Header */}
          <div className="bg-blue-600 text-white p-6">
            <h1 className="text-xl font-bold">Reschedule Appointment</h1>
            <p className="text-blue-100 mt-1">{calendarName}</p>
          </div>

          {/* Current booking info */}
          <div className="p-6 border-b">
            <h2 className="text-sm font-medium text-gray-500 uppercase mb-3">Current Appointment</h2>
            <div className="flex items-center gap-3 text-gray-700">
              <CalendarDays className="w-5 h-5 text-gray-400" />
              <span>{booking?.start_time ? new Date(booking.start_time).toLocaleString() : 'N/A'}</span>
            </div>
            <div className="flex items-center gap-3 text-gray-700 mt-2">
              <Clock className="w-5 h-5 text-gray-400" />
              <span>{durationMinutes} minutes</span>
            </div>
          </div>

          {/* Date picker */}
          <div className="p-6 border-b">
            <h2 className="text-sm font-medium text-gray-500 uppercase mb-3">Select New Date</h2>
            <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto">
              {dates.map((date) => {
                const d = new Date(date + 'T12:00:00')
                const isWeekend = d.getDay() === 0 || d.getDay() === 6
                return (
                  <button
                    key={date}
                    onClick={() => { setSelectedDate(date); setSelectedSlot('') }}
                    disabled={isWeekend}
                    className={`
                      py-2 px-1 rounded-lg text-sm font-medium transition-colors
                      ${selectedDate === date ? 'bg-blue-600 text-white' : ''}
                      ${isWeekend ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-blue-50 text-gray-700'}
                    `}
                  >
                    <div className="text-xs">{d.toLocaleDateString(undefined, { weekday: 'short' })}</div>
                    <div>{d.getDate()}</div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Time slots */}
          {selectedDate && (
            <div className="p-6 border-b">
              <h2 className="text-sm font-medium text-gray-500 uppercase mb-3">Select Time</h2>
              {loadingSlots ? (
                <p className="text-sm text-gray-500">Loading available times...</p>
              ) : slots.length === 0 ? (
                <p className="text-sm text-gray-500">No available slots on this date.</p>
              ) : (
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                  {slots.map((slot: any) => {
                    const startTime = new Date(slot.start)
                    return (
                      <button
                        key={slot.start}
                        onClick={() => setSelectedSlot(slot.start)}
                        className={`
                          py-2 px-3 rounded-lg text-sm font-medium transition-colors
                          ${selectedSlot === slot.start ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-blue-50 text-gray-700'}
                        `}
                      >
                        {startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Submit */}
          <div className="p-6">
            {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
            <button
              onClick={handleReschedule}
              disabled={!selectedSlot || submitting}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-3 rounded-lg font-medium
                         hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Rescheduling...' : (
                <>Reschedule <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
