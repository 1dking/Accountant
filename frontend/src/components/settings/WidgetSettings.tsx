import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Copy, RefreshCw, MessageCircle } from 'lucide-react'
import { widgetApi, type WidgetConfig } from '@/api/widget'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

const INPUT =
  'w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100'

type Draft = Partial<WidgetConfig>

export default function WidgetSettings() {
  const { t } = useTranslation('ui')
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
      toast.success(t('ui:WidgetSettings.widgetSaved'))
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Failed to save'),
  })

  const rotateMutation = useMutation({
    mutationFn: () => widgetApi.rotateKey(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-widget'] })
      toast.success(t('ui:WidgetSettings.widgetKeyRotatedUpdateYour'))
    },
  })

  if (isLoading || !widget) {
    return <div className="text-gray-500">{t('ui:WidgetSettings.loadingWidgetSettings')}</div>
  }

  const set = (field: keyof WidgetConfig, value: unknown) => setDraft((d) => ({ ...d, [field]: value }))
  const snippet = `<script src="${window.location.origin}/widget.js" data-widget-key="${widget.widget_key}" async></script>`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('ui:WidgetSettings.embedWidget')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
           {t('ui:WidgetSettings.aFloatingContactUsWidget')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={!!draft.is_enabled} onChange={(e) => set('is_enabled', e.target.checked)} />
           {t('ui:WidgetSettings.enabled')}
          </label>
          <button
            onClick={() => saveMutation.mutate(draft)}
            disabled={saveMutation.isPending}
            className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 hover:opacity-90"
            style={{ background: 'var(--brand-primary)' }}
          >
            {saveMutation.isPending ? t('ui:WidgetSettings.saving') : t('ui:WidgetSettings.save')}
          </button>
        </div>
      </div>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:WidgetSettings.appearance')}</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:WidgetSettings.mode')}</label>
            <select value={draft.mode ?? 'floating'} onChange={(e) => set('mode', e.target.value)} className={INPUT}>
              <option value="floating">{t('ui:WidgetSettings.floatingButton')}</option>
              <option value="inline">{t('ui:WidgetSettings.inline')}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:WidgetSettings.position')}</label>
            <select value={draft.position ?? 'bottom-right'} onChange={(e) => set('position', e.target.value)} className={INPUT}>
              <option value="bottom-right">{t('ui:WidgetSettings.bottomRight')}</option>
              <option value="bottom-left">{t('ui:WidgetSettings.bottomLeft')}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:WidgetSettings.buttonColor')}</label>
            <input
              type="color"
              value={draft.button_color || '#2563eb'}
              onChange={(e) => set('button_color', e.target.value)}
              className="h-9 w-full rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('ui:WidgetSettings.panelBackground')}</label>
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
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:WidgetSettings.copy')}</h3>
        <input value={draft.greeting_title ?? ''} onChange={(e) => set('greeting_title', e.target.value)} placeholder={t('ui:WidgetSettings.letSTalk')} className={INPUT} />
        <textarea
          value={draft.greeting_message ?? ''}
          onChange={(e) => set('greeting_message', e.target.value)}
          rows={2}
          placeholder={t('ui:WidgetSettings.leaveYourDetailsAndWe')}
          className={INPUT}
        />
        <textarea
          value={draft.success_message ?? ''}
          onChange={(e) => set('success_message', e.target.value)}
          rows={2}
          placeholder={t('ui:WidgetSettings.thanksWeLlBeIn')}
          className={INPUT}
        />
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" checked={!!draft.collect_phone} onChange={(e) => set('collect_phone', e.target.checked)} />
         {t('ui:WidgetSettings.collectPhoneNumber')}
        </label>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:WidgetSettings.embedSnippet')}</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">
         {t('ui:WidgetSettings.pasteThisBefore')} <code>&lt;/body&gt;</code> {t('ui:WidgetSettings.onAnyWebsiteYouWant')}
        </p>
        <textarea readOnly value={snippet} rows={2} className={`${INPUT} font-mono text-xs`} />
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(snippet)
              toast.success(t('ui:WidgetSettings.snippetCopied'))
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <Copy className="w-3.5 h-3.5" /> {t('ui:WidgetSettings.copySnippet')}
          </button>
          <button
            onClick={() => {
              if (confirm(t('ui:WidgetSettings.rotateTheWidgetKeyAny'))) {
                rotateMutation.mutate()
              }
            }}
            disabled={rotateMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md text-red-600 border-red-200 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50"
          >
            <RefreshCw className="w-3.5 h-3.5" /> {t('ui:WidgetSettings.rotateKey')}
          </button>
        </div>
      </section>

      <section className="bg-white dark:bg-gray-900 border rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{t('ui:WidgetSettings.preview')}</h3>
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
