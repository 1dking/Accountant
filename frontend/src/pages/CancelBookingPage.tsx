import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import { schedulingApi } from '@/api/scheduling'
import { CalendarDays, Clock, XCircle, Check, AlertCircle } from 'lucide-react'

export default function CancelBookingPage() {
  const { token } = useParams<{ token: string }>()
  const [booking, setBooking] = useState<any>(null)
  const [calendarName, setCalendarName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (!token) return
    schedulingApi.getCancelInfo(token)
      .then((res: any) => {
        const data = res.data?.data || res.data
        setBooking(data.booking)
        setCalendarName(data.calendar_name)
      })
      .catch(() => setError('This cancellation link is invalid or has expired.'))
      .finally(() => setLoading(false))
  }, [token])

  const handleCancel = async () => {
    if (!token) return
    setSubmitting(true)
    try {
      await schedulingApi.cancelBookingByToken(token, reason || undefined)
      setSuccess(true)
    } catch {
      setError('Failed to cancel. Please try again.')
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
          <h1 className="text-xl font-bold text-gray-900 mb-2">Appointment Cancelled</h1>
          <p className="text-gray-600">Your appointment has been cancelled successfully.</p>
          <p className="text-sm text-gray-500 mt-4">We hope to see you again soon.</p>
        </div>
      </div>
    )
  }

  const isCancelled = booking?.status === 'cancelled'

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-lg mx-auto">
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          {/* Header */}
          <div className="bg-red-600 text-white p-6">
            <h1 className="text-xl font-bold">Cancel Appointment</h1>
            <p className="text-red-100 mt-1">{calendarName}</p>
          </div>

          {/* Booking info */}
          <div className="p-6 border-b">
            <h2 className="text-sm font-medium text-gray-500 uppercase mb-3">Appointment Details</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-gray-700">
                <CalendarDays className="w-5 h-5 text-gray-400" />
                <span>{booking?.start_time ? new Date(booking.start_time).toLocaleString() : 'N/A'}</span>
              </div>
              <div className="flex items-center gap-3 text-gray-700">
                <Clock className="w-5 h-5 text-gray-400" />
                <span>
                  {booking?.start_time && booking?.end_time
                    ? `${Math.round((new Date(booking.end_time).getTime() - new Date(booking.start_time).getTime()) / 60000)} minutes`
                    : 'N/A'}
                </span>
              </div>
              {booking?.meeting_type && (
                <div className="text-sm text-gray-600">
                  Type: {booking.meeting_type.replace('_', ' ')}
                </div>
              )}
            </div>
          </div>

          {isCancelled ? (
            <div className="p-6 text-center">
              <XCircle className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-600">This appointment has already been cancelled.</p>
            </div>
          ) : (
            <>
              {/* Reason */}
              <div className="p-6 border-b">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Reason for cancellation (optional)
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  placeholder="Let us know why you're cancelling..."
                />
              </div>

              {/* Submit */}
              <div className="p-6">
                {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
                <button
                  onClick={handleCancel}
                  disabled={submitting}
                  className="w-full flex items-center justify-center gap-2 bg-red-600 text-white py-3 rounded-lg font-medium
                             hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {submitting ? 'Cancelling...' : (
                    <>Cancel Appointment <XCircle className="w-4 h-4" /></>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
