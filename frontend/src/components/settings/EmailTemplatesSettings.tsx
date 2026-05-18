import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Mail, RotateCcw, Send } from 'lucide-react'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'

interface Template {
  template_key: string
  label: string
  description: string
  default_subject: string
  variables: string[]
  allows_body_override: boolean
  warnings: string[]
  subject_override: string | null
  body_override: string | null
  is_customized: boolean
  system_body: string
}

export default function EmailTemplatesSettings() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [showSystemBody, setShowSystemBody] = useState(false)
  const [testEmail, setTestEmail] = useState(user?.email || '')

  const { data, isLoading } = useQuery({
    queryKey: ['email-templates'],
    queryFn: () => api.get<{ data: Template[] }>('/email/templates'),
  })

  const templates = data?.data || []
  const active = templates.find((t) => t.template_key === activeKey) || null

  // Default-select the first template once data loads.
  useEffect(() => {
    if (!activeKey && templates.length > 0) {
      setActiveKey(templates[0].template_key)
    }
  }, [templates, activeKey])

  // When the selected template changes, reset the editor to its saved
  // values (or empty strings if no override).
  useEffect(() => {
    if (active) {
      setDraftSubject(active.subject_override || '')
      setDraftBody(active.body_override || '')
      setShowSystemBody(false)
    }
  }, [active?.template_key])

  const saveMut = useMutation({
    mutationFn: (vars: { key: string; subject: string; body: string }) =>
      api.put(`/email/templates/${vars.key}`, {
        subject_override: vars.subject || null,
        body_override: vars.body || null,
      }),
    onSuccess: () => {
      toast.success('Template saved')
      queryClient.invalidateQueries({ queryKey: ['email-templates'] })
    },
    onError: (e: any) => toast.error(`Save failed: ${e.message || ''}`),
  })

  const resetMut = useMutation({
    mutationFn: (key: string) => api.delete(`/email/templates/${key}`),
    onSuccess: () => {
      toast.success('Reverted to system default')
      setDraftSubject('')
      setDraftBody('')
      queryClient.invalidateQueries({ queryKey: ['email-templates'] })
    },
    onError: (e: any) => toast.error(`Reset failed: ${e.message || ''}`),
  })

  const testMut = useMutation({
    mutationFn: (vars: { key: string; to: string; subject: string; body: string }) =>
      api.post(`/email/templates/${vars.key}/test`, {
        to_email: vars.to,
        subject_override: vars.subject || null,
        body_override: vars.body || null,
      }),
    onSuccess: () => toast.success('Test sent — check your inbox'),
    onError: (e: any) => toast.error(`Test failed: ${e.message || ''}`),
  })

  const insertPlaceholder = (variable: string) => {
    const token = `{${variable}}`
    setDraftBody((prev) => prev + token)
  }

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400">Loading…</div>
    )
  }

  return (
    <div className="space-y-4">
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start gap-3 mb-4">
          <Mail className="h-5 w-5 text-indigo-500 mt-0.5" />
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">
              Email templates
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 max-w-2xl">
              Customize the subject and body of system emails. Use{' '}
              <code className="font-mono text-[11px] bg-gray-100 dark:bg-gray-800 px-1 rounded">{`{placeholder}`}</code>{' '}
              tokens to inject runtime values. Leaving a field blank falls
              back to the system default.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
          {/* Template list */}
          <div className="space-y-1">
            {templates.map((t) => (
              <button
                key={t.template_key}
                onClick={() => setActiveKey(t.template_key)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  t.template_key === activeKey
                    ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 font-medium'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span>{t.label}</span>
                  {t.is_customized && (
                    <span className="text-[10px] uppercase tracking-wide text-indigo-600 dark:text-indigo-400">
                      custom
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Editor */}
          {active && (
            <div className="space-y-4 min-w-0">
              <div>
                <h3 className="text-base font-medium text-gray-900 dark:text-gray-100">
                  {active.label}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {active.description}
                </p>
              </div>

              {active.warnings?.length > 0 && (
                <div className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 px-3 py-2 rounded-md">
                  {active.warnings.map((w, i) => (
                    <p key={i}>{w}</p>
                  ))}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  value={draftSubject}
                  onChange={(e) => setDraftSubject(e.target.value)}
                  placeholder={active.default_subject}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100 dark:bg-gray-800 text-sm"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Default: <span className="font-mono">{active.default_subject}</span>
                </p>
              </div>

              {active.allows_body_override ? (
                <>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Body (HTML)
                      </label>
                      <button
                        type="button"
                        onClick={() => setShowSystemBody((s) => !s)}
                        className="text-xs text-blue-600 hover:text-blue-700"
                      >
                        {showSystemBody ? 'Hide' : 'Show'} system default
                      </button>
                    </div>
                    <textarea
                      value={draftBody}
                      onChange={(e) => setDraftBody(e.target.value)}
                      placeholder="Leave blank to use the system default"
                      rows={14}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100 dark:bg-gray-800 text-sm font-mono"
                    />
                    {showSystemBody && (
                      <pre className="text-[11px] mt-2 max-h-64 overflow-auto p-3 bg-gray-50 dark:bg-gray-800 rounded-md text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                        {active.system_body}
                      </pre>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Available placeholders (click to insert into body):
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {active.variables.map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => insertPlaceholder(v)}
                          className="text-xs font-mono px-2 py-1 bg-gray-100 dark:bg-gray-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/30 rounded border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                        >
                          {`{${v}}`}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 px-3 py-2 rounded-md">
                  Body editing is disabled for this template. Subject is
                  editable above.
                </p>
              )}

              {/* Actions */}
              <div className="flex flex-col gap-3 pt-2 border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      saveMut.mutate({
                        key: active.template_key,
                        subject: draftSubject,
                        body: draftBody,
                      })
                    }
                    disabled={saveMut.isPending}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm disabled:opacity-50"
                  >
                    {saveMut.isPending ? 'Saving…' : 'Save changes'}
                  </button>
                  {active.is_customized && (
                    <button
                      type="button"
                      onClick={() => {
                        if (
                          confirm(
                            'Revert this template to the system default? Your override will be deleted.',
                          )
                        ) {
                          resetMut.mutate(active.template_key)
                        }
                      }}
                      disabled={resetMut.isPending}
                      className="px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md inline-flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Reset to default
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                  <input
                    type="email"
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="flex-1 max-w-xs px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-900 dark:text-gray-100 dark:bg-gray-800"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      testMut.mutate({
                        key: active.template_key,
                        to: testEmail,
                        subject: draftSubject,
                        body: draftBody,
                      })
                    }
                    disabled={testMut.isPending || !testEmail}
                    className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md inline-flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Send className="w-3.5 h-3.5" />
                    {testMut.isPending ? 'Sending…' : 'Send test'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
