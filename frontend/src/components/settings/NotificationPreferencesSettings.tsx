import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BellRing } from 'lucide-react'
import { api } from '@/api/client'
import { useTranslation } from 'react-i18next'

interface PrefItem {
  type: string
  label: string
  in_app: boolean
  email: boolean
  sms: boolean
}

interface PrefPayload {
  items: PrefItem[]
  fallback_phone: string | null
}

export default function NotificationPreferencesSettings() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [items, setItems] = useState<PrefItem[]>([])

  const { data, isLoading } = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: () => api.get<{ data: PrefPayload }>('/notifications/preferences'),
  })

  useEffect(() => {
    if (data?.data?.items) setItems(data.data.items)
  }, [data])

  const fallbackPhone = data?.data?.fallback_phone || null
  const smsChannelDisabled = !fallbackPhone

  const saveMut = useMutation({
    mutationFn: (next: PrefItem[]) =>
      api.put('/notifications/preferences', {
        items: next.map((i) => ({
          type: i.type,
          in_app: i.in_app,
          email: i.email,
          sms: i.sms,
        })),
      }),
    onSuccess: () => {
      toast.success(t('ui:NotificationPreferencesSettings.preferencesSaved'))
      queryClient.invalidateQueries({ queryKey: ['notification-preferences'] })
    },
    onError: (e: any) => toast.error(t('ui:NotificationPreferencesSettings.saveFailedV0', { v0: e.message || '' })),
  })

  const toggle = (idx: number, channel: 'in_app' | 'email' | 'sms') => {
    const next = items.map((it, i) =>
      i === idx ? { ...it, [channel]: !it[channel] } : it,
    )
    setItems(next)
  }

  const dirty =
    JSON.stringify(items.map((i) => [i.type, i.in_app, i.email, i.sms])) !==
    JSON.stringify(
      (data?.data?.items ?? []).map((i) => [i.type, i.in_app, i.email, i.sms]),
    )

  return (
    <div className="space-y-4">
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start gap-3 mb-4">
          <BellRing className="h-5 w-5 text-indigo-500 mt-0.5" />
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">
             {t('ui:NotificationPreferencesSettings.notificationPreferences')}
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 max-w-lg">
             {t('ui:NotificationPreferencesSettings.chooseHowYouReceiveEach')}
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="text-sm text-gray-500">{t('ui:NotificationPreferencesSettings.loading')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-700 text-left">
                  <th className="px-3 py-2 font-medium text-gray-600 dark:text-gray-400">
                   {t('ui:NotificationPreferencesSettings.event')}
                  </th>
                  <th className="px-3 py-2 font-medium text-gray-600 dark:text-gray-400 text-center">
                   {t('ui:NotificationPreferencesSettings.inApp')}
                  </th>
                  <th className="px-3 py-2 font-medium text-gray-600 dark:text-gray-400 text-center">
                   {t('ui:NotificationPreferencesSettings.email')}
                  </th>
                  <th className="px-3 py-2 font-medium text-gray-600 dark:text-gray-400 text-center">
                   {t('ui:NotificationPreferencesSettings.smsToCell')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr
                    key={item.type}
                    className="border-b border-gray-50 dark:border-gray-800"
                  >
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100">
                      {item.label}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={item.in_app}
                        onChange={() => toggle(idx, 'in_app')}
                      />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={item.email}
                        onChange={() => toggle(idx, 'email')}
                      />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={item.sms && !smsChannelDisabled}
                        disabled={smsChannelDisabled}
                        onChange={() => toggle(idx, 'sms')}
                        title={
                          smsChannelDisabled
                            ? t('ui:NotificationPreferencesSettings.setAFallbackPhoneIn')
                            : undefined
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
         {t('ui:NotificationPreferencesSettings.emailNotificationsAreSentVia')}
        </p>
        {smsChannelDisabled && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
           {t('ui:NotificationPreferencesSettings.addAFallbackPhoneNumber')}{' '}
            <a href="/settings?tab=profile" className="underline">
             {t('ui:NotificationPreferencesSettings.profile')}
            </a>{' '}
           {t('ui:NotificationPreferencesSettings.toEnableSmsNotifications')}
          </p>
        )}

        <div className="flex items-center gap-3 mt-4">
          <button
            type="button"
            onClick={() => saveMut.mutate(items)}
            disabled={!dirty || saveMut.isPending}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm disabled:opacity-50"
          >
            {saveMut.isPending ? t('ui:NotificationPreferencesSettings.saving') : t('ui:NotificationPreferencesSettings.savePreferences')}
          </button>
          {dirty && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
             {t('ui:NotificationPreferencesSettings.unsavedChanges')}
            </span>
          )}
        </div>
      </section>
    </div>
  )
}
