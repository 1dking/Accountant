/**
 * BlockFieldsPanel — block model v2 "Fields" drawer.
 *
 * Renders inputs from the variant's `fields_schema` (the same contract the
 * AI fills), edits `metadata.props`, and PATCHes `{ props }` on save. The
 * backend validates, re-renders `jsx_content` from the template and
 * recompiles. Saving discards any inline edits (`edited_html`) because
 * they were made against the previous render — we confirm first.
 *
 * Field types: text | textarea | number | color | url | select | boolean |
 * image (via MediaPickerModal) | list (add / remove / reorder, nested
 * item_fields).
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  X, Loader2, Plus, Trash2, ChevronUp, ChevronDown, Image as ImageIcon, SlidersHorizontal,
} from 'lucide-react'
import { pagesApi } from '@/api/pages'
import MediaPickerModal from './MediaPickerModal'
import type { PageSection } from './SectionEditor'

export interface FieldDef {
  key: string
  type: 'text' | 'textarea' | 'number' | 'color' | 'url' | 'select' | 'boolean' | 'image' | 'list'
  label?: string
  label_fr?: string
  hint?: string
  required?: boolean
  max_len?: number
  min?: number
  max?: number
  options?: string[]
  default?: unknown
  min_items?: number
  max_items?: number
  item_fields?: FieldDef[]
}

interface VariantRow {
  variant_id: string
  category: string
  display_name: string
  schema_version?: number
  fields_schema?: FieldDef[]
  default_props?: Record<string, unknown>
}

interface Props {
  open: boolean
  pageId: string
  sectionIndex: number
  section: PageSection
  onSaved: () => void
  onClose: () => void
}

type Values = Record<string, unknown>

function labelFor(f: FieldDef, lang: string): string {
  if (lang.startsWith('fr') && f.label_fr) return f.label_fr
  return f.label || f.key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function BlockFieldsPanel({ open, pageId, sectionIndex, section, onSaved, onClose }: Props) {
  const { t, i18n } = useTranslation('ui')
  const queryClient = useQueryClient()
  const variantId: string | undefined = section.metadata?.variant_id
  const category = section.type || 'hero'

  const variantsQ = useQuery({
    queryKey: ['section-variants', category],
    queryFn: () => pagesApi.listVariants(category) as Promise<{ data: VariantRow[] }>,
    enabled: open && !!variantId,
    staleTime: 60_000,
  })
  const variant = useMemo(
    () => variantsQ.data?.data?.find(v => v.variant_id === variantId) ?? null,
    [variantsQ.data, variantId],
  )
  const schema: FieldDef[] = variant?.fields_schema ?? []

  const [values, setValues] = useState<Values>({})
  const [dirty, setDirty] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [imageSlot, setImageSlot] = useState<{ path: string; current: string } | null>(null)

  // (Re)seed local state from the section whenever the drawer opens.
  useEffect(() => {
    if (!open) return
    setValues({ ...(variant?.default_props ?? {}), ...((section.metadata?.props as Values) ?? {}) })
    setDirty(false)
    setErrors([])
  }, [open, section.metadata?.props, variant?.default_props])

  const saveMut = useMutation({
    mutationFn: (props: Values) =>
      pagesApi.patchSection(pageId, sectionIndex, { props }) as Promise<{ field_errors?: string[] }>,
    onSuccess: (resp) => {
      const fe = resp?.field_errors ?? []
      setErrors(fe)
      if (fe.length) toast.warning(t('ui:BlockFieldsPanel.savedWithWarnings', { count: fe.length }))
      else toast.success(t('ui:BlockFieldsPanel.saved'))
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ['page', pageId] })
      onSaved()
    },
    onError: (e: any) => toast.error(t('ui:BlockFieldsPanel.saveFailed', { v0: e?.message || 'unknown' })),
  })

  const handleSave = () => {
    if (section.edited_html && !window.confirm(t('ui:BlockFieldsPanel.confirmDiscardInlineEdits'))) return
    saveMut.mutate(values)
  }

  // ---- generic getters/setters by dotted path (LIST.2.NAME) ---------------
  const getAt = (obj: unknown, path: string): unknown =>
    path.split('.').reduce<any>((acc, k) => (acc == null ? undefined : acc[k]), obj)
  const setAt = (path: string, val: unknown) => {
    setValues(prev => {
      const next: any = structuredClone(prev)
      const parts = path.split('.')
      let cur = next
      for (let i = 0; i < parts.length - 1; i++) {
        const k = parts[i]
        if (cur[k] == null) cur[k] = /^\d+$/.test(parts[i + 1]) ? [] : {}
        cur = cur[k]
      }
      cur[parts[parts.length - 1]] = val
      return next
    })
    setDirty(true)
  }

  const renderField = (f: FieldDef, path: string, depth = 0) => {
    const id = `bf-${path.replace(/\./g, '-')}`
    const val = getAt(values, path)
    const label = labelFor(f, i18n.language)
    const base = 'w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2.5 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500'
    const wrap = (control: ReactNode) => (
      <div key={path} className={depth ? 'mb-2' : 'mb-3'}>
        <label htmlFor={id} className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
          {label}{f.required && <span className="text-rose-500 ml-0.5">*</span>}
          {f.max_len && f.type !== 'list' && typeof val === 'string' && (
            <span className="float-right font-normal text-gray-400">{val.length}/{f.max_len}</span>
          )}
        </label>
        {control}
        {f.hint && <p className="mt-0.5 text-[11px] text-gray-400">{f.hint}</p>}
      </div>
    )

    switch (f.type) {
      case 'textarea':
        return wrap(
          <textarea id={id} className={`${base} min-h-[72px]`} maxLength={f.max_len}
            value={(val as string) ?? ''} onChange={e => setAt(path, e.target.value)} />,
        )
      case 'number':
        return wrap(
          <input id={id} type="number" className={base} min={f.min} max={f.max}
            value={val == null ? '' : String(val)} onChange={e => setAt(path, e.target.value === '' ? null : Number(e.target.value))} />,
        )
      case 'color':
        return wrap(
          <div className="flex items-center gap-2">
            <input id={id} type="color" className="h-8 w-10 rounded border border-gray-300 dark:border-gray-600 bg-transparent"
              value={typeof val === 'string' && /^#[0-9a-f]{6}$/i.test(val) ? val : '#000000'} onChange={e => setAt(path, e.target.value)} />
            <input type="text" className={base} value={(val as string) ?? ''} onChange={e => setAt(path, e.target.value)} placeholder="#RRGGBB" />
          </div>,
        )
      case 'select':
        return wrap(
          <select id={id} className={base} value={(val as string) ?? ''} onChange={e => setAt(path, e.target.value)}>
            {!f.required && <option value="">—</option>}
            {(f.options ?? []).map(o => <option key={o} value={o}>{o}</option>)}
          </select>,
        )
      case 'boolean':
        return (
          <label key={path} className="flex items-center gap-2 mb-3 text-sm text-gray-700 dark:text-gray-200">
            <input id={id} type="checkbox" checked={!!val} onChange={e => setAt(path, e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
            {label}
          </label>
        )
      case 'image':
        return wrap(
          <div className="flex items-center gap-2">
            <div className="h-10 w-14 shrink-0 rounded border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 overflow-hidden flex items-center justify-center">
              {typeof val === 'string' && val
                ? <img src={val} alt="" className="h-full w-full object-cover" />
                : <ImageIcon className="h-4 w-4 text-gray-400" />}
            </div>
            <input id={id} type="text" className={base} value={(val as string) ?? ''} onChange={e => setAt(path, e.target.value)} placeholder="https://…" />
            <button type="button" onClick={() => setImageSlot({ path, current: (val as string) ?? '' })}
              className="shrink-0 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700">
              {t('ui:BlockFieldsPanel.choose')}
            </button>
          </div>,
        )
      case 'list': {
        const items: unknown[] = Array.isArray(val) ? val : []
        const canAdd = !f.max_items || items.length < f.max_items
        const itemFields = f.item_fields ?? [{ key: 'VALUE', type: 'text' as const }]
        return (
          <fieldset key={path} className="mb-4 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
            <legend className="px-1 text-xs font-semibold text-gray-600 dark:text-gray-300">
              {label} <span className="font-normal text-gray-400">({items.length}{f.max_items ? `/${f.max_items}` : ''})</span>
            </legend>
            {items.map((_, i) => (
              <div key={i} className="mb-2 rounded-md bg-gray-50 dark:bg-gray-800/60 p-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-medium text-gray-500">#{i + 1}</span>
                  <div className="flex items-center gap-1">
                    <button type="button" disabled={i === 0} aria-label={t('ui:BlockFieldsPanel.moveUp')}
                      onClick={() => { const n = [...items]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; setAt(path, n) }}
                      className="p-1 rounded text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
                    <button type="button" disabled={i === items.length - 1} aria-label={t('ui:BlockFieldsPanel.moveDown')}
                      onClick={() => { const n = [...items]; [n[i + 1], n[i]] = [n[i], n[i + 1]]; setAt(path, n) }}
                      className="p-1 rounded text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
                    <button type="button" aria-label={t('ui:BlockFieldsPanel.remove')}
                      onClick={() => setAt(path, items.filter((__, j) => j !== i))}
                      className="p-1 rounded text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/30"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
                {itemFields.map(sub => renderField(sub, `${path}.${i}.${sub.key}`, depth + 1))}
              </div>
            ))}
            <button type="button" disabled={!canAdd}
              onClick={() => setAt(path, [...items, Object.fromEntries(itemFields.map(sf => [sf.key, sf.default ?? (sf.type === 'list' ? [] : '')]))])}
              className="mt-1 inline-flex items-center gap-1 rounded-md border border-dashed border-gray-300 dark:border-gray-600 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40">
              <Plus className="h-3.5 w-3.5" /> {t('ui:BlockFieldsPanel.addItem')}
            </button>
          </fieldset>
        )
      }
      default: // text | url
        return wrap(
          <input id={id} type={f.type === 'url' ? 'text' : 'text'} className={base} maxLength={f.max_len}
            value={(val as string) ?? ''} onChange={e => setAt(path, e.target.value)}
            placeholder={f.type === 'url' ? 'https://… or #anchor' : undefined} />,
        )
    }
  }

  if (!open) return null

  return (
    <div className="absolute inset-y-0 right-0 z-30 w-[360px] max-w-full flex flex-col border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl" role="dialog" aria-label={t('ui:BlockFieldsPanel.title')}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-indigo-500" />
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('ui:BlockFieldsPanel.title')}</p>
            <p className="text-[11px] text-gray-500">{variant?.display_name ?? variantId}</p>
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label={t('ui:BlockFieldsPanel.close')} className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {!variantId ? (
          <p className="text-sm text-gray-500">{t('ui:BlockFieldsPanel.noVariant')}</p>
        ) : variantsQ.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500"><Loader2 className="h-4 w-4 animate-spin" /> {t('ui:BlockFieldsPanel.loading')}</div>
        ) : schema.length === 0 ? (
          <p className="text-sm text-gray-500">{t('ui:BlockFieldsPanel.noFields')}</p>
        ) : (
          <>
            {section.edited_html && (
              <p className="mb-3 rounded-md bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-200">
                {t('ui:BlockFieldsPanel.inlineEditsWarning')}
              </p>
            )}
            {errors.length > 0 && (
              <ul className="mb-3 rounded-md bg-rose-50 dark:bg-rose-900/20 px-3 py-2 text-[11px] text-rose-700 dark:text-rose-200 list-disc list-inside">
                {errors.map(e => <li key={e}>{e}</li>)}
              </ul>
            )}
            {schema.map(f => renderField(f, f.key))}
          </>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <button type="button" onClick={onClose} className="rounded-md px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800">
          {t('ui:BlockFieldsPanel.cancel')}
        </button>
        <button type="button" onClick={handleSave} disabled={!dirty || saveMut.isPending || schema.length === 0}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          {saveMut.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t('ui:BlockFieldsPanel.save')}
        </button>
      </div>

      <MediaPickerModal
        open={imageSlot !== null}
        tokenName={imageSlot ? imageSlot.path.split('.').pop()!.replace(/_URL$/, '') : ''}
        slotKind="image"
        currentValue={imageSlot?.current ?? null}
        onClose={() => setImageSlot(null)}
        onPick={(url) => { if (imageSlot) setAt(imageSlot.path, url); setImageSlot(null) }}
      />
    </div>
  )
}
