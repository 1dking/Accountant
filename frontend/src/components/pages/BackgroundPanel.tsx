/**
 * Section background drawer — image, looping video or gradient behind a
 * block, with a colour overlay, position, blur, parallax / fixed options.
 * Writes `background` on the section (PATCH); the compiler and the editor
 * iframe render the same layer (renderBackgroundLayer).
 */
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { X, Loader2, Image as ImageIcon, Film, Paintbrush, Ban } from 'lucide-react'
import { pagesApi } from '@/api/pages'
import MediaPickerModal from './MediaPickerModal'
import type { SectionBackground } from './SectionEditor'

interface Props {
  open: boolean
  pageId: string
  sectionIndex: number
  value: SectionBackground | null | undefined
  onPreview: (bg: SectionBackground | null) => void
  onSaved: () => void
  onClose: () => void
}

const GRADIENTS = [
  'linear-gradient(135deg, #4f46e5, #7c3aed)',
  'linear-gradient(135deg, #0f172a, #1e293b)',
  'linear-gradient(135deg, #f97316, #ec4899)',
  'linear-gradient(135deg, #10b981, #06b6d4)',
  'radial-gradient(circle at 30% 20%, #6366f1, #0f172a 70%)',
]

const EMPTY: SectionBackground = { type: 'none', overlay_color: '#000000', overlay_opacity: 0.4, position: 'center', parallax: false, fixed: false, blur: 0 }

export default function BackgroundPanel({ open, pageId, sectionIndex, value, onPreview, onSaved, onClose }: Props) {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const [bg, setBg] = useState<SectionBackground>(value ? { ...EMPTY, ...value } : EMPTY)
  const [picker, setPicker] = useState<'image' | 'video' | 'poster' | null>(null)

  useEffect(() => { if (open) setBg(value ? { ...EMPTY, ...value } : EMPTY) }, [open, value])

  const update = (patch: Partial<SectionBackground>) => {
    const next = { ...bg, ...patch }
    setBg(next)
    onPreview(next.type === 'none' ? null : next)
  }

  const save = useMutation({
    mutationFn: (b: SectionBackground | null) => pagesApi.patchSection(pageId, sectionIndex, { background: b }),
    onSuccess: () => { toast.success(t('ui:BackgroundPanel.saved')); qc.invalidateQueries({ queryKey: ['page', pageId] }); onSaved(); onClose() },
    onError: (e: any) => toast.error(t('ui:BackgroundPanel.saveFailed', { v0: e?.message || 'unknown' })),
  })

  if (!open) return null
  const ready = bg.type === 'none' || (bg.type === 'gradient' && !!bg.gradient) || ((bg.type === 'image' || bg.type === 'video') && !!bg.url)
  const input = 'w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2.5 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500'
  const types: { key: SectionBackground['type']; label: string; Icon: typeof ImageIcon }[] = [
    { key: 'none', label: t('ui:BackgroundPanel.none'), Icon: Ban },
    { key: 'image', label: t('ui:BackgroundPanel.image'), Icon: ImageIcon },
    { key: 'video', label: t('ui:BackgroundPanel.video'), Icon: Film },
    { key: 'gradient', label: t('ui:BackgroundPanel.gradient'), Icon: Paintbrush },
  ]

  return (
    <div className="absolute inset-y-0 right-0 z-30 w-[340px] max-w-full flex flex-col border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl" role="dialog" aria-label={t('ui:BackgroundPanel.title')}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:BackgroundPanel.title')}</p>
        <button type="button" onClick={onClose} aria-label={t('ui:BackgroundPanel.close')} className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"><X className="h-4 w-4" /></button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        <div className="grid grid-cols-4 gap-1.5">
          {types.map(({ key, label, Icon }) => (
            <button key={key} type="button" onClick={() => update({ type: key, gradient: key === 'gradient' && !bg.gradient ? GRADIENTS[0] : bg.gradient })}
              className={`flex flex-col items-center gap-1 rounded-lg border px-1 py-2 text-[11px] ${bg.type === key ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-200' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}`}>
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </div>

        {(bg.type === 'image' || bg.type === 'video') && (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300">{bg.type === 'video' ? t('ui:BackgroundPanel.videoUrl') : t('ui:BackgroundPanel.imageUrl')}</label>
            <div className="flex gap-2">
              <input className={input} value={bg.url ?? ''} onChange={e => update({ url: e.target.value })} placeholder={bg.type === 'video' ? 'https://… .mp4 / YouTube' : 'https://…'} />
              <button type="button" onClick={() => setPicker(bg.type === 'video' ? 'video' : 'image')} className="shrink-0 rounded-md border border-gray-300 dark:border-gray-600 px-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">{t('ui:BackgroundPanel.choose')}</button>
            </div>
            {bg.type === 'video' && (
              <>
                <p className="rounded-md bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1.5 text-[11px] text-amber-800 dark:text-amber-200">{t('ui:BackgroundPanel.hostedVideoHint')}</p>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-300">{t('ui:BackgroundPanel.poster')}</label>
                <div className="flex gap-2">
                  <input className={input} value={bg.poster ?? ''} onChange={e => update({ poster: e.target.value })} placeholder="https://…" />
                  <button type="button" onClick={() => setPicker('poster')} className="shrink-0 rounded-md border border-gray-300 dark:border-gray-600 px-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">{t('ui:BackgroundPanel.choose')}</button>
                </div>
              </>
            )}
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300">{t('ui:BackgroundPanel.position')}</label>
            <select className={input} value={bg.position ?? 'center'} onChange={e => update({ position: e.target.value as SectionBackground['position'] })}>
              {['center', 'top', 'bottom', 'left', 'right'].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300">{t('ui:BackgroundPanel.blur')} <span className="text-gray-400">{bg.blur ?? 0}px</span></label>
            <input type="range" min={0} max={20} value={bg.blur ?? 0} onChange={e => update({ blur: Number(e.target.value) })} className="w-full" />
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200"><input type="checkbox" checked={!!bg.parallax} onChange={e => update({ parallax: e.target.checked, fixed: e.target.checked ? false : bg.fixed })} className="h-4 w-4 rounded border-gray-300" /> {t('ui:BackgroundPanel.parallax')}</label>
            {bg.type === 'image' && (
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200"><input type="checkbox" checked={!!bg.fixed} onChange={e => update({ fixed: e.target.checked, parallax: e.target.checked ? false : bg.parallax })} className="h-4 w-4 rounded border-gray-300" /> {t('ui:BackgroundPanel.fixed')}</label>
            )}
          </div>
        )}

        {bg.type === 'gradient' && (
          <div className="space-y-2">
            <div className="grid grid-cols-5 gap-1.5">
              {GRADIENTS.map(g => (
                <button key={g} type="button" onClick={() => update({ gradient: g })} aria-label={g}
                  className={`h-9 rounded-md border-2 ${bg.gradient === g ? 'border-indigo-500' : 'border-transparent'}`} style={{ background: g }} />
              ))}
            </div>
            <input className={input} value={bg.gradient ?? ''} onChange={e => update({ gradient: e.target.value })} placeholder="linear-gradient(135deg, #4f46e5, #7c3aed)" />
          </div>
        )}

        {bg.type !== 'none' && (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300">{t('ui:BackgroundPanel.overlay')} <span className="text-gray-400">{Math.round((bg.overlay_opacity ?? 0) * 100)}%</span></label>
            <div className="flex items-center gap-2">
              <input type="color" value={bg.overlay_color ?? '#000000'} onChange={e => update({ overlay_color: e.target.value })} className="h-8 w-10 rounded border border-gray-300 dark:border-gray-600 bg-transparent" />
              <input type="range" min={0} max={100} value={Math.round((bg.overlay_opacity ?? 0) * 100)} onChange={e => update({ overlay_opacity: Number(e.target.value) / 100 })} className="flex-1" />
            </div>
            <p className="text-[11px] text-gray-400">{t('ui:BackgroundPanel.overlayHint')}</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <button type="button" onClick={() => { onPreview(value ?? null); onClose() }} className="rounded-md px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800">{t('ui:BackgroundPanel.cancel')}</button>
        <button type="button" disabled={!ready || save.isPending} onClick={() => save.mutate(bg.type === 'none' ? null : bg)}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          {save.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />} {t('ui:BackgroundPanel.save')}
        </button>
      </div>

      <MediaPickerModal
        open={picker !== null}
        tokenName={picker === 'poster' ? 'POSTER' : 'BACKGROUND'}
        slotKind={picker === 'video' ? 'video' : 'image'}
        currentValue={picker === 'poster' ? (bg.poster ?? '') : (bg.url ?? '')}
        onClose={() => setPicker(null)}
        onPick={(url) => { if (picker === 'poster') update({ poster: url }); else update({ url }); setPicker(null) }}
      />
    </div>
  )
}
