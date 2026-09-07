import { Bell, BellOff, BellRing } from 'lucide-react'
import { usePushNotifications } from '@/hooks/usePushNotifications'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

export default function PushNotificationSettings() {
  const { t } = useTranslation('ui')
  const { isSupported, permission, isSubscribed, loading, subscribe, unsubscribe } = usePushNotifications()

  const handleToggle = async () => {
    if (isSubscribed) {
      await unsubscribe()
      toast.success(t('ui:PushNotificationSettings.pushNotificationsDisabled'))
    } else {
      const ok = await subscribe()
      if (ok) {
        toast.success(t('ui:PushNotificationSettings.pushNotificationsEnabled'))
      } else if (permission === 'denied') {
        toast.error(t('ui:PushNotificationSettings.notificationsBlockedEnableThemIn'))
      }
    }
  }

  if (!isSupported) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:PushNotificationSettings.pushNotifications')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
           {t('ui:PushNotificationSettings.receiveNotificationsEvenWhenThe')}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border p-6 text-center">
          <BellOff className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600 dark:text-gray-300">
           {t('ui:PushNotificationSettings.pushNotificationsAreNotSupported')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:PushNotificationSettings.pushNotifications')}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:PushNotificationSettings.receiveNotificationsEvenWhenThe')}
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isSubscribed ? (
              <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <BellRing className="w-5 h-5 text-green-600" />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                <Bell className="w-5 h-5 text-gray-500" />
              </div>
            )}
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {isSubscribed ? t('ui:PushNotificationSettings.pushNotificationsEnabled_2') : t('ui:PushNotificationSettings.pushNotificationsDisabled_2')}
              </p>
              <p className="text-sm text-gray-500">
                {isSubscribed
                  ? t('ui:PushNotificationSettings.youLlReceiveNotificationsOn')
                  : t('ui:PushNotificationSettings.enableToGetNotifiedAbout')}
              </p>
            </div>
          </div>

          <button
            onClick={handleToggle}
            disabled={loading}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${isSubscribed
                ? 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                : 'bg-blue-600 text-white hover:bg-blue-700'}
              disabled:opacity-50
            `}
          >
            {loading ? t('ui:PushNotificationSettings.processing') : isSubscribed ? t('ui:PushNotificationSettings.disable') : t('ui:PushNotificationSettings.enable')}
          </button>
        </div>

        {permission === 'denied' && (
          <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
            <p className="text-sm text-amber-700 dark:text-amber-300">
             {t('ui:PushNotificationSettings.notificationsAreBlockedByYour')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
