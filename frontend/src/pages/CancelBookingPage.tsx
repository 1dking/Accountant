import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import { schedulingApi } from '@/api/scheduling'
import { CalendarDays, Clock, XCircle, Check, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function CancelBookingPage() {
  const { t } = useTranslation('ui')
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
      .catch(() => setError(t('ui:CancelBookingPage.thisCancellationLinkIsInvalid')))
      .finally(() => setLoading(false))
  }, [token])

  const handleCancel = async () => {
    if (!token) return
    setSubmitting(true)
    try {
      await schedulingApi.cancelBookingByToken(token, reason || undefined)
      setSuccess(true)
    } catch {
      setError(t('ui:CancelBookingPage.failedToCancelPleaseTry'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="animate-pulse text-gray-500 dark:text-gray-400">{t('ui:CancelBookingPage.loading')}</div>
      </div>
    )
  }

  if (error && !booking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg p-8 max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">{t('ui:CancelBookingPage.linkInvalid')}</h1>
          <p className="text-gray-600 dark:text-gray-400">{error}</p>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg p-8 max-w-md text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">{t('ui:CancelBookingPage.appointmentCancelled')}</h1>
          <p className="text-gray-600 dark:text-gray-400">{t('ui:CancelBookingPage.yourAppointmentHasBeenCancelled')}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">{t('ui:CancelBookingPage.weHopeToSeeYou')}</p>
        </div>
      </div>
    )
  }

  const isCancelled = booking?.status === 'cancelled'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 py-8 px-4">
      <div className="max-w-lg mx-auto">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg overflow-hidden">
          {/* Header */}
          <div className="bg-red-600 text-white p-6">
            <h1 className="text-xl font-bold">{t('ui:CancelBookingPage.cancelAppointment')}</h1>
            <p className="text-red-100 mt-1">{calendarName}</p>
          </div>

          {/* Booking info */}
          <div className="p-6 border-b">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase mb-3">{t('ui:CancelBookingPage.appointmentDetails')}</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-gray-700 dark:text-gray-300">
                <CalendarDays className="w-5 h-5 text-gray-400 dark:text-gray-500" />
                <span>{booking?.start_time ? new Date(booking.start_time).toLocaleString() : 'N/A'}</span>
              </div>
              <div className="flex items-center gap-3 text-gray-700 dark:text-gray-300">
                <Clock className="w-5 h-5 text-gray-400 dark:text-gray-500" />
                <span>
                  {booking?.start_time && booking?.end_time
                    ? t('ui:CancelBookingPage.v0Minutes', { v0: Math.round((new Date(booking.end_time).getTime() - new Date(booking.start_time).getTime()) / 60000) })
                    : 'N/A'}
                </span>
              </div>
              {booking?.meeting_type && (
                <div className="text-sm text-gray-600 dark:text-gray-400">
                 {t('ui:CancelBookingPage.type')} {booking.meeting_type.replace('_', ' ')}
                </div>
              )}
            </div>
          </div>

          {isCancelled ? (
            <div className="p-6 text-center">
              <XCircle className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-3" />
              <p className="text-gray-600 dark:text-gray-400">{t('ui:CancelBookingPage.thisAppointmentHasAlreadyBeen')}</p>
            </div>
          ) : (
            <>
              {/* Reason */}
              <div className="p-6 border-b">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                 {t('ui:CancelBookingPage.reasonForCancellationOptional')}
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="w-full border border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  placeholder={t('ui:CancelBookingPage.letUsKnowWhyYou')}
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
                  {submitting ? t('ui:CancelBookingPage.cancelling') : (
                    <>{t('ui:CancelBookingPage.cancelAppointment')} <XCircle className="w-4 h-4" /></>
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
