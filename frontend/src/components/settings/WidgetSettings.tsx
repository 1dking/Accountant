import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Copy, RefreshCw, MessageCircle } from 'lucide-react'
import { widgetApi, type WidgetConfig } from '@/api/widget'
import { toast } from 'sonner'

const INPUT =
  'w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100'

type Draft = Partial<WidgetConfig>

export default function WidgetSettings() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>({})
  const [syncedId, setSyncedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['my-widget'],
    queryFn: () => widgetApi.getMyWidget(),
  })
  const widget = data?.data

  if (widget && widget.id !== syncedId) {
    setSyncedId(widget.id)
    setDraft(widget)
  }

  const saveMutation = useMutation({
    mutationFn: (payload: Draft) => widgetApi.updateMyWidget(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-widget'] })
      toast.success('Widget saved')
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Failed to save'),
  })

  const rotateMutation = useMutation({
    mutationFn: () => widgetApi.rotateKey(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-widget'] })
      toast.success('Widget key rotated — update your embed snippet everywhere it\'s used')
    },
  })

  if (isLoading || !widget) {
    return <div className="text-gray-500">Loading widget settings…</div>
  }

  const set = (field: keyof WidgetConfig, value: unknown) => setDraft((d) => ({ ...d, [field]: value }))
  const snippet = `<script src="${window.location.origin}/widget.js" data-widget-key="${widget.widget_key}" async></script>`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Embed Widget</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            A floating "Contact us" widget you can drop into any website — leads land straight in your Contacts and can trigger workflows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={!!draft.is_enabled} onChange={(e) => set('is_enabled', e.target.checked)} />
            Enabled
          </label>
          <button
            onClick={() => saveMutation.mutate(draft)}
            disabled={saveMutation.isPending}
            className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
            style={{ background: 'var(--brand-primary)' }}
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Appearance</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Mode</label>
            <select value={draft.mode ?? 'floating'} onChange={(e) => set('mode', e.target.value)} className={INPUT}>
              <option value="floating">Floating button</option>
              <option value="inline">Inline</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Position</label>
            <select value={draft.position ?? 'bottom-right'} onChange={(e) => set('position', e.target.value)} className={INPUT}>
              <option value="bottom-right">Bottom right</option>
              <option value="bottom-left">Bottom left</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Button color</label>
            <input
              type="color"
              value={draft.button_color || '#2563eb'}
              onChange={(e) => set('button_color', e.target.value)}
              className="h-9 w-full rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Panel background</label>
            <input
              type="color"
              value={draft.bg_color || '#ffffff'}
              onChange={(e) => set('bg_color', e.target.value)}
              className="h-9 w-full rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
            />
          </div>
        </div>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Copy</h3>
        <input value={draft.greeting_title ?? ''} onChange={(e) => set('greeting_title', e.target.value)} placeholder="Let's talk" className={INPUT} />
        <textarea
          value={draft.greeting_message ?? ''}
          onChange={(e) => set('greeting_message', e.target.value)}
          rows={2}
          placeholder="Leave your details and we'll get back to you shortly."
          className={INPUT}
        />
        <textarea
          value={draft.success_message ?? ''}
          onChange={(e) => set('success_message', e.target.value)}
          rows={2}
          placeholder="Thanks! We'll be in touch soon."
          className={INPUT}
        />
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" checked={!!draft.collect_phone} onChange={(e) => set('collect_phone', e.target.checked)} />
          Collect phone number
        </label>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Embed snippet</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Paste this before <code>&lt;/body&gt;</code> on any website you want the widget to appear on.
        </p>
        <textarea readOnly value={snippet} rows={2} className={`${INPUT} font-mono text-xs`} />
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(snippet)
              toast.success('Snippet copied')
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <Copy className="w-3.5 h-3.5" /> Copy snippet
          </button>
          <button
            onClick={() => {
              if (confirm('Rotate the widget key? Any site using the current snippet will stop working until you update it.')) {
                rotateMutation.mutate()
              }
            }}
            disabled={rotateMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md text-red-600 border-red-200 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Rotate key
          </button>
        </div>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Preview</h3>
        <div className="relative bg-gray-100 dark:bg-gray-950 rounded-lg h-40 flex items-end justify-end p-4">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center shadow-lg"
            style={{ background: draft.button_color || '#2563eb' }}
          >
            <MessageCircle className="w-6 h-6 text-white" />
          </div>
        </div>
      </section>
    </div>
  )
}
