import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Save } from 'lucide-react'
import { listSmsLogs, sendSms, getIntegrationSettings, saveIntegrationSettings } from '@/api/integrations'
import { formatDate } from '@/lib/utils'
import { useTranslation } from 'react-i18next'

const statusColors: Record<string, string> = {
  sent: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700',
  delivered: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

export default function SmsSettings() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [to, setTo] = useState('')
  const [message, setMessage] = useState('')
  const [msg, setMsg] = useState('')

  // Config form
  const [configForm, setConfigForm] = useState({
    account_sid: '',
    auth_token: '',
    from_number: '',
    api_key_sid: '',
    api_key_secret: '',
    twiml_app_sid: '',
  })
  const [configLoaded, setConfigLoaded] = useState(false)

  const { data: configData } = useQuery({
    queryKey: ['integration-settings', 'twilio'],
    queryFn: () => getIntegrationSettings('twilio'),
  })

  // Populate form when config loads
  if (configData && !configLoaded) {
    setConfigForm({
      account_sid: configData.data?.account_sid || '',
      auth_token: configData.data?.auth_token || '',
      from_number: configData.data?.from_number || '',
      api_key_sid: configData.data?.api_key_sid || '',
      api_key_secret: configData.data?.api_key_secret || '',
      twiml_app_sid: configData.data?.twiml_app_sid || '',
    })
    setConfigLoaded(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => saveIntegrationSettings('twilio', configForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-settings', 'twilio'] })
      setConfigLoaded(false)
      setMsg(t('ui:SmsSettings.twilioSettingsSaved'))
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg(t('ui:SmsSettings.failedToSaveSettings'))
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const { data } = useQuery({
    queryKey: ['sms-logs'],
    queryFn: listSmsLogs,
  })

  const sendMutation = useMutation({
    mutationFn: () => sendSms(to, message),
    onSuccess: () => {
      setMsg(t('ui:SmsSettings.smsSent'))
      setTo('')
      setMessage('')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg(t('ui:SmsSettings.failedToSendSmsCheck'))
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const logs = data?.data ?? []
  const isConfigured = configData?.meta?.is_configured ?? false

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('ui:SmsSettings.smsNotificationsTwilio')}</h2>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Twilio Config Form */}
      <form
        onSubmit={(e) => { e.preventDefault(); saveMutation.mutate() }}
        className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ui:SmsSettings.twilioConfiguration')}</h3>
          {isConfigured && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">{t('ui:SmsSettings.configured')}</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.accountSid')}</label>
            <input
              type="text"
              value={configForm.account_sid}
              onChange={(e) => setConfigForm({ ...configForm, account_sid: e.target.value })}
              placeholder={t('ui:SmsSettings.acxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')}
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.authToken')}</label>
            <input
              type="password"
              value={configForm.auth_token}
              onChange={(e) => setConfigForm({ ...configForm, auth_token: e.target.value })}
              placeholder={t('ui:SmsSettings.yourAuthToken')}
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.fromNumberLegacyFallback')}</label>
            <input
              type="tel"
              value={configForm.from_number}
              onChange={(e) => setConfigForm({ ...configForm, from_number: e.target.value })}
              placeholder="+1234567890"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="pt-3 border-t border-gray-100 dark:border-gray-800">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">
           {t('ui:SmsSettings.voiceAccesstokenTwimlApp')}
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.apiKeySid')}</label>
              <input
                type="text"
                value={configForm.api_key_sid}
                onChange={(e) => setConfigForm({ ...configForm, api_key_sid: e.target.value })}
                placeholder={t('ui:SmsSettings.skxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.apiKeySecret')}</label>
              <input
                type="password"
                value={configForm.api_key_secret}
                onChange={(e) => setConfigForm({ ...configForm, api_key_secret: e.target.value })}
                placeholder={t('ui:SmsSettings.shownOnceAtCreation')}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.twimlAppSid')}</label>
              <input
                type="text"
                value={configForm.twiml_app_sid}
                onChange={(e) => setConfigForm({ ...configForm, twiml_app_sid: e.target.value })}
                placeholder={t('ui:SmsSettings.apxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')}
                className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saveMutation.isPending ? t('ui:SmsSettings.saving') : t('ui:SmsSettings.saveConfiguration')}
        </button>
      </form>

      {/* Send test SMS */}
      <div className="bg-white dark:bg-gray-900 border rounded-lg p-5">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{t('ui:SmsSettings.sendTestSms')}</h3>
        <div className="flex gap-2">
          <input
            type="tel"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="+1234567890"
            className="w-40 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('ui:SmsSettings.testMessage')}
            className="flex-1 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => sendMutation.mutate()}
            disabled={!to || !message || sendMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
           {t('ui:SmsSettings.send')}
          </button>
        </div>
      </div>

      {/* SMS Logs */}
      {logs.length > 0 && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ui:SmsSettings.smsHistory')}</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 dark:bg-gray-950">
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('ui:SmsSettings.recipient')}</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('ui:SmsSettings.message')}</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('ui:SmsSettings.status')}</th>
                <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">{t('ui:SmsSettings.date')}</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 20).map((log) => (
                <tr key={log.id} className="border-b">
                  <td className="px-4 py-2 text-gray-900 dark:text-gray-100">{log.recipient}</td>
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-400 max-w-xs truncate">{log.message}</td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[log.status] || 'bg-gray-100 dark:bg-gray-800 text-gray-600'}`}>
                      {log.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{formatDate(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:SmsSettings.smsFeatures')}</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>{t('ui:SmsSettings.sendInvoiceSummariesWithPayment')}</li>
          <li>{t('ui:SmsSettings.overduePaymentReminders')}</li>
          <li>{t('ui:SmsSettings.paymentConfirmationNotifications')}</li>
          <li>{t('ui:SmsSettings.customSmsMessages')}</li>
        </ul>
      </div>
    </div>
  )
}
