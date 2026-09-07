import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { CalendarDays, Link2, Unlink, RefreshCw, Check } from 'lucide-react'
import { googleCalendarApi } from '@/api/googleCalendar'
import { useTranslation } from 'react-i18next'

interface GCalAccount {
  id: string
  email: string
  is_active: boolean
  last_sync_at: string | null
  selected_calendar_id: string | null
}

interface GCalendar {
  id: string
  summary: string
  description: string | null
  primary: boolean
  background_color: string | null
}

export default function GoogleCalendarSettings() {
  const { t } = useTranslation('ui')
  const [accounts, setAccounts] = useState<GCalAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [calendars, setCalendars] = useState<Record<string, GCalendar[]>>({})
  const [loadingCalendars, setLoadingCalendars] = useState<string | null>(null)

  const fetchAccounts = async () => {
    try {
      const res: any = await googleCalendarApi.listAccounts()
      setAccounts(res.data?.data || [])
    } catch {
      // No accounts yet
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
  }, [])

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const res: any = await googleCalendarApi.connect()
      const authUrl = res.data?.data?.auth_url
      if (authUrl) {
        window.location.href = authUrl
      }
    } catch {
      toast.error(t('ui:GoogleCalendarSettings.failedToStartGoogleCalendar'))
      setConnecting(false)
    }
  }

  const handleDisconnect = async (accountId: string) => {
    try {
      await googleCalendarApi.disconnectAccount(accountId)
      setAccounts((prev) => prev.filter((a) => a.id !== accountId))
      toast.success(t('ui:GoogleCalendarSettings.googleCalendarDisconnected'))
    } catch {
      toast.error(t('ui:GoogleCalendarSettings.failedToDisconnect'))
    }
  }

  const handleLoadCalendars = async (accountId: string) => {
    setLoadingCalendars(accountId)
    try {
      const res: any = await googleCalendarApi.listCalendars(accountId)
      setCalendars((prev) => ({ ...prev, [accountId]: res.data?.data || [] }))
    } catch {
      toast.error(t('ui:GoogleCalendarSettings.failedToLoadCalendars'))
    } finally {
      setLoadingCalendars(null)
    }
  }

  const handleSetSyncCalendar = async (accountId: string, calendarId: string) => {
    try {
      await googleCalendarApi.setSyncCalendar(accountId, calendarId)
      setAccounts((prev) =>
        prev.map((a) =>
          a.id === accountId ? { ...a, selected_calendar_id: calendarId } : a
        )
      )
      toast.success(t('ui:GoogleCalendarSettings.syncCalendarUpdated'))
    } catch {
      toast.error(t('ui:GoogleCalendarSettings.failedToSetSyncCalendar'))
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      const res: any = await googleCalendarApi.triggerSync()
      const result = res.data?.data
      toast.success(t('ui:GoogleCalendarSettings.syncedV0EventsPulled', { v0: result?.events_pulled || 0 }))
      fetchAccounts()
    } catch {
      toast.error(t('ui:GoogleCalendarSettings.syncFailed'))
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return <div className="text-gray-500 p-4">{t('ui:GoogleCalendarSettings.loading')}</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:GoogleCalendarSettings.googleCalendar')}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:GoogleCalendarSettings.connectYourGoogleCalendarTo')}
        </p>
      </div>

      {accounts.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border p-6 text-center">
          <CalendarDays className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600 dark:text-gray-300 mb-4">{t('ui:GoogleCalendarSettings.noGoogleCalendarConnectedYet')}</p>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Link2 className="w-4 h-4" />
            {connecting ? t('ui:GoogleCalendarSettings.connecting') : t('ui:GoogleCalendarSettings.connectGoogleCalendar')}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {accounts.map((account) => (
            <div key={account.id} className="bg-white dark:bg-gray-800 rounded-lg border p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">{account.email}</p>
                  <p className="text-xs text-gray-500">
                   {t('ui:GoogleCalendarSettings.lastSynced')} {account.last_sync_at
                      ? new Date(account.last_sync_at).toLocaleString()
                      : t('ui:GoogleCalendarSettings.never')}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                   {t('ui:GoogleCalendarSettings.sync')}
                  </button>
                  <button
                    onClick={() => handleDisconnect(account.id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    <Unlink className="w-3.5 h-3.5" />
                   {t('ui:GoogleCalendarSettings.disconnect')}
                  </button>
                </div>
              </div>

              {/* Calendar selection */}
              {!calendars[account.id] ? (
                <button
                  onClick={() => handleLoadCalendars(account.id)}
                  disabled={loadingCalendars === account.id}
                  className="text-sm text-blue-600 hover:underline"
                >
                  {loadingCalendars === account.id ? t('ui:GoogleCalendarSettings.loadingCalendars') : t('ui:GoogleCalendarSettings.selectSyncCalendar')}
                </button>
              ) : (
                <div className="mt-3 border-t pt-3">
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">{t('ui:GoogleCalendarSettings.syncWith')}</p>
                  <div className="space-y-1">
                    {calendars[account.id].map((cal) => (
                      <button
                        key={cal.id}
                        onClick={() => handleSetSyncCalendar(account.id, cal.id)}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                          account.selected_calendar_id === cal.id
                            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {cal.background_color && (
                          <div
                            className="w-3 h-3 rounded-full shrink-0"
                            style={{ backgroundColor: cal.background_color }}
                          />
                        )}
                        <span className="truncate">{cal.summary}</span>
                        {cal.primary && <span className="text-xs text-gray-400">{t('ui:GoogleCalendarSettings.primary')}</span>}
                        {account.selected_calendar_id === cal.id && (
                          <Check className="w-4 h-4 text-blue-600 ml-auto shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}

          <button
            onClick={handleConnect}
            disabled={connecting}
            className="text-sm text-blue-600 hover:underline"
          >
           {t('ui:GoogleCalendarSettings.connectAnotherAccount')}
          </button>
        </div>
      )}
    </div>
  )
}
