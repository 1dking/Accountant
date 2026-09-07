/**
 * Platform Admin → Blocks: the block library (block model v2).
 * Toggle blocks on/off (a disabled block leaves every picker and the AI
 * planner), re-seed from code, render thumbnails.
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { Loader2, RefreshCw, Camera, Search, Power, Sparkles, ImageOff } from 'lucide-react'
import { platformAdminApi } from '@/api/platformAdmin'
import SectionThumb from './SectionThumb'
import { pagesApi } from '@/api/pages'

interface Block {
  id: string
  category: string
  variant_id: string
  display_name: string
  description: string | null
  sort_order: number
  is_active: boolean
  schema_version: number
  behaviour: string | null
  data_source: string | null
  motion_preset: string | null
  capabilities: string[]
  field_count: number
  locales: string[]
  preview_thumbnail_url: string | null
  thumbnail_rendered_at: string | null
  thumbnail_stale: boolean
}
interface BlocksResponse {
  data: Block[]
  meta: { categories: Record<string, { total: number; active: number; with_thumbnail: number }>; total: number; render: { running: boolean; last: unknown } }
}

export default function BlocksAdminTab() {
  const { t } = useTranslation('ui')
  const qc = useQueryClient()
  const [filter, setFilter] = useState('')
  const [category, setCategory] = useState<string>('all')
  const [onlyDynamic, setOnlyDynamic] = useState(false)

  const q = useQuery({ queryKey: ['platform-admin', 'blocks'], queryFn: () => platformAdminApi.listBlocks() as Promise<BlocksResponse>, refetchInterval: (query) => (query.state.data?.meta.render.running ? 3000 : false) })
  // preview_html for blocks without a rendered thumbnail (same call the pickers use)
  const lib = useQuery({ queryKey: ['section-variants', 'all'], queryFn: () => pagesApi.listVariants() as Promise<{ data: { id: string; preview_html?: string }[] }>, staleTime: 60_000 })
  const previews = useMemo(() => new Map((lib.data?.data ?? []).map(v => [v.id, v.preview_html])), [lib.data])

  const invalidate = () => qc.invalidateQueries({ queryKey: ['platform-admin', 'blocks'] })
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { is_active?: boolean } }) => platformAdminApi.patchBlock(id, body),
    onSuccess: () => { invalidate(); qc.invalidateQueries({ queryKey: ['section-variants'] }) },
    onError: (e: any) => toast.error(e?.message || 'Failed'),
  })
  const resync = useMutation({
    mutationFn: () => platformAdminApi.resyncBlocks() as Promise<{ data: { synced: number } }>,
    onSuccess: (r) => { toast.success(t('ui:BlocksAdminTab.resynced', { count: r.data.synced })); invalidate(); qc.invalidateQueries({ queryKey: ['section-variants'] }) },
    onError: (e: any) => toast.error(e?.message || 'Failed'),
  })
  const renderOne = useMutation({
    mutationFn: (id: string) => platformAdminApi.renderBlockThumbnail(id),
    onSuccess: () => { toast.success(t('ui:BlocksAdminTab.thumbnailRendered')); invalidate() },
    onError: (e: any) => toast.error(e?.status === 501 ? t('ui:BlocksAdminTab.playwrightMissing') : (e?.message || 'Failed')),
  })
  const renderAll = useMutation({
    mutationFn: (force: boolean) => platformAdminApi.renderAllThumbnails(force),
    onSuccess: () => { toast.success(t('ui:BlocksAdminTab.renderStarted')); invalidate() },
    onError: (e: any) => toast.error(e?.status === 501 ? t('ui:BlocksAdminTab.playwrightMissing') : (e?.message || 'Failed')),
  })

  const blocks = q.data?.data ?? []
  const categories = Object.keys(q.data?.meta.categories ?? {})
  const shown = blocks.filter(b =>
    (category === 'all' || b.category === category)
    && (!onlyDynamic || b.capabilities.some(c => c !== 'static'))
    && (!filter.trim() || `${b.display_name} ${b.variant_id} ${b.description ?? ''}`.toLowerCase().includes(filter.toLowerCase())),
  )
  const running = q.data?.meta.render.running
  const withThumb = blocks.filter(b => b.preview_thumbnail_url).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{t('ui:BlocksAdminTab.title')}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t('ui:BlocksAdminTab.summary', { total: blocks.length, active: blocks.filter(b => b.is_active).length, thumbs: withThumb })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => resync.mutate()} disabled={resync.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50">
            {resync.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} {t('ui:BlocksAdminTab.resync')}
          </button>
          <button onClick={() => renderAll.mutate(false)} disabled={renderAll.isPending || !!running}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />} {running ? t('ui:BlocksAdminTab.rendering') : t('ui:BlocksAdminTab.renderThumbnails')}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-600 px-2.5 py-1.5 bg-white dark:bg-gray-800">
          <Search className="h-3.5 w-3.5 text-gray-400" />
          <input value={filter} onChange={e => setFilter(e.target.value)} placeholder={t('ui:BlocksAdminTab.search')} className="bg-transparent text-sm outline-none text-gray-900 dark:text-gray-100 w-48" />
        </div>
        <select value={category} onChange={e => setCategory(e.target.value)} className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2.5 py-1.5 text-sm text-gray-900 dark:text-gray-100">
          <option value="all">{t('ui:BlocksAdminTab.allCategories')}</option>
          {categories.map(c => <option key={c} value={c}>{c} ({q.data!.meta.categories[c].active}/{q.data!.meta.categories[c].total})</option>)}
        </select>
        <label className="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-200">
          <input type="checkbox" checked={onlyDynamic} onChange={e => setOnlyDynamic(e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
          <Sparkles className="h-3.5 w-3.5 text-indigo-500" /> {t('ui:BlocksAdminTab.dynamicOnly')}
        </label>
      </div>

      {q.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500"><Loader2 className="h-4 w-4 animate-spin" /> {t('ui:BlocksAdminTab.loading')}</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map(b => (
            <div key={b.id} className={`rounded-xl border overflow-hidden bg-white dark:bg-gray-900 ${b.is_active ? 'border-gray-200 dark:border-gray-700' : 'border-dashed border-gray-300 dark:border-gray-600 opacity-70'}`}>
              <div className="relative bg-gray-100 dark:bg-gray-800">
                {b.preview_thumbnail_url ? (
                  <img src={b.preview_thumbnail_url} alt={b.display_name} className="w-full aspect-[16/10] object-cover object-top" />
                ) : previews.get(b.id) ? (
                  <SectionThumb html={previews.get(b.id)!} ratio={1.6} />
                ) : (
                  <div className="aspect-[16/10] flex items-center justify-center text-gray-400"><ImageOff className="h-6 w-6" /></div>
                )}
                <div className="absolute top-2 left-2 flex gap-1">
                  <span className="rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">{b.category}</span>
                  {b.behaviour && <span className="rounded bg-indigo-600/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">{b.behaviour}</span>}
                  {b.data_source && <span className="rounded bg-emerald-600/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">{b.data_source}</span>}
                </div>
                {b.thumbnail_stale && b.preview_thumbnail_url && (
                  <span className="absolute top-2 right-2 rounded bg-amber-500/90 px-1.5 py-0.5 text-[10px] font-semibold text-white">{t('ui:BlocksAdminTab.stale')}</span>
                )}
              </div>
              <div className="p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{b.display_name}</p>
                    <p className="text-[11px] text-gray-500 truncate">{b.variant_id} · v{b.schema_version} · {b.field_count} {t('ui:BlocksAdminTab.fields')}{b.locales.length ? ` · ${b.locales.join(', ')}` : ''}</p>
                  </div>
                  <button onClick={() => patch.mutate({ id: b.id, body: { is_active: !b.is_active } })} title={b.is_active ? t('ui:BlocksAdminTab.disable') : t('ui:BlocksAdminTab.enable')}
                    className={`shrink-0 rounded-md p-1.5 ${b.is_active ? 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30' : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
                    <Power className="h-4 w-4" />
                  </button>
                </div>
                {b.description && <p className="mt-1 text-xs text-gray-500 line-clamp-2">{b.description}</p>}
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[11px] text-gray-400">{b.thumbnail_rendered_at ? new Date(b.thumbnail_rendered_at).toLocaleString() : t('ui:BlocksAdminTab.noThumbnail')}</span>
                  <button onClick={() => renderOne.mutate(b.id)} disabled={renderOne.isPending} className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:underline disabled:opacity-50">
                    <Camera className="h-3 w-3" /> {t('ui:BlocksAdminTab.render')}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
