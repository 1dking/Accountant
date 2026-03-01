import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Send, Star } from 'lucide-react'
import { listSmtpConfigs, createSmtpConfig, deleteSmtpConfig, sendTestEmail } from '@/api/integrations'
import type { SmtpConfig } from '@/types/models'

export default function SmtpSettings() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [testEmail, setTestEmail] = useState('')
  const [testConfigId, setTestConfigId] = useState<string | null>(null)
  const [msg, setMsg] = useState('')

  const [form, setForm] = useState({
    name: '', host: '', port: 587, username: '', password: '',
    from_email: '', from_name: '', use_tls: true, is_default: false,
  })

  const { data } = useQuery({
    queryKey: ['smtp-configs'],
    queryFn: listSmtpConfigs,
  })

  const createMutation = useMutation({
    mutationFn: () => createSmtpConfig(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['smtp-configs'] })
      setShowForm(false)
      setForm({ name: '', host: '', port: 587, username: '', password: '', from_email: '', from_name: '', use_tls: true, is_default: false })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSmtpConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['smtp-configs'] }),
  })

  const testMutation = useMutation({
    mutationFn: ({ configId, email }: { configId: string; email: string }) =>
      sendTestEmail(configId, email),
    onSuccess: () => {
      setMsg('Test email sent!')
      setTestConfigId(null)
      setTestEmail('')
      setTimeout(() => setMsg(''), 3000)
    },
    onError: () => {
      setMsg('Failed to send test email')
      setTimeout(() => setMsg(''), 3000)
    },
  })

  const configs: SmtpConfig[] = data?.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">SMTP Email Configuration</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Add Config
        </button>
      </div>

      {msg && (
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">{msg}</div>
      )}

      {showForm && (
        <form
          onSubmit={(e) => { e.preventDefault(); createMutation.mutate() }}
          className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
              <input type="text" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="e.g., Company SMTP" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Host</label>
              <input type="text" required value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="smtp.gmail.com" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Port</label>
              <input type="number" required value={form.port} onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
              <input type="text" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">From Email</label>
              <input type="email" required value={form.from_email} onChange={(e) => setForm({ ...form, from_email: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">From Name</label>
              <input type="text" required value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.use_tls} onChange={(e) => setForm({ ...form, use_tls: e.target.checked })} />
              Use TLS
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
              Set as default
            </label>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={createMutation.isPending}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {createMutation.isPending ? 'Saving...' : 'Save Configuration'}
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">Cancel</button>
          </div>
        </form>
      )}

      {/* Config list */}
      <div className="space-y-3">
        {configs.map((config) => (
          <div key={config.id} className="bg-white dark:bg-gray-900 border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100">{config.name}</h3>
                  {config.is_default && (
                    <span className="flex items-center gap-1 text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                      <Star className="w-3 h-3" /> Default
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {config.host}:{config.port} &middot; {config.from_email}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setTestConfigId(config.id); setTestEmail('') }}
                  className="flex items-center gap-1 px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <Send className="w-3 h-3" /> Test
                </button>
                <button
                  onClick={() => { if (confirm('Delete this SMTP config?')) deleteMutation.mutate(config.id) }}
                  className="p-1 text-red-500 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {testConfigId === config.id && (
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="test@example.com"
                  className="flex-1 px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={() => testMutation.mutate({ configId: config.id, email: testEmail })}
                  disabled={!testEmail || testMutation.isPending}
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {testMutation.isPending ? 'Sending...' : 'Send Test'}
                </button>
                <button onClick={() => setTestConfigId(null)} className="px-2 py-1.5 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800">
                  Cancel
                </button>
              </div>
            )}
          </div>
        ))}

        {configs.length === 0 && !showForm && (
          <p className="text-center text-gray-400 dark:text-gray-500 py-8 text-sm">
            No SMTP configurations yet. Add one to start sending emails.
          </p>
        )}
      </div>
    </div>
  )
}
