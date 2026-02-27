import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Save } from 'lucide-react'
import { listSmsLogs, sendSms, getIntegrationSettings, saveIntegrationSettings } from '@/api/integrations'
import { formatDate } from '@/lib/utils'

const statusColors: Record<string, string> = {
  sent: 'bg-blue-100 text-blue-700',
  delivered: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

export default function SmsSettings() {
  const queryClient = useQueryClient()
  const [to, setTo] = useState('')
  const [message, setMessage] = useState('')
  const [msg, setMsg] = useState('')

  // Config form
  const [configForm, setConfigForm] = useState({
    account_sid: '',
    auth_token: '',
    from_number: '',
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
    })
    setConfigLoaded(true)
  }

  const saveMutation = useMutation({
    mutationFn: () => saveIntegrationSettings('twilio', configForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-settings', 'twilio'] })
      setConfigLoaded(false)
      setMsg('Twilio settings saved!')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg('Failed to save settings')
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
      setMsg('SMS sent!')
      setTo('')
      setMessage('')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg('Failed to send SMS. Check Twilio configuration.')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const logs = data?.data ?? []
  const isConfigured = configData?.meta?.is_configured ?? false

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-gray-900">SMS Notifications (Twilio)</h2>

      {msg && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {/* Twilio Config Form */}
      <form
        onSubmit={(e) => { e.preventDefault(); saveMutation.mutate() }}
        className="bg-white border rounded-lg p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700">Twilio Configuration</h3>
          {isConfigured && (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Configured</span>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Account SID</label>
            <input
              type="text"
              value={configForm.account_sid}
              onChange={(e) => setConfigForm({ ...configForm, account_sid: e.target.value })}
              placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Auth Token</label>
            <input
              type="password"
              value={configForm.auth_token}
              onChange={(e) => setConfigForm({ ...configForm, auth_token: e.target.value })}
              placeholder="Your auth token"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From Number</label>
            <input
              type="tel"
              value={configForm.from_number}
              onChange={(e) => setConfigForm({ ...configForm, from_number: e.target.value })}
              placeholder="+1234567890"
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
        </button>
      </form>

      {/* Send test SMS */}
      <div className="bg-white border rounded-lg p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Send Test SMS</h3>
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
            placeholder="Test message..."
            className="flex-1 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => sendMutation.mutate()}
            disabled={!to || !message || sendMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>

      {/* SMS Logs */}
      {logs.length > 0 && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="px-5 py-3 border-b">
            <h3 className="text-sm font-medium text-gray-700">SMS History</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Recipient</th>
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Message</th>
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Status</th>
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice(0, 20).map((log) => (
                <tr key={log.id} className="border-b">
                  <td className="px-4 py-2 text-gray-900">{log.recipient}</td>
                  <td className="px-4 py-2 text-gray-600 max-w-xs truncate">{log.message}</td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[log.status] || 'bg-gray-100 text-gray-600'}`}>
                      {log.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-500">{formatDate(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-600">
        <h4 className="font-medium text-gray-700 mb-1">SMS Features</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500">
          <li>Send invoice summaries with payment links via SMS</li>
          <li>Overdue payment reminders</li>
          <li>Payment confirmation notifications</li>
          <li>Custom SMS messages</li>
        </ul>
      </div>
    </div>
  )
}
