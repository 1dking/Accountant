/**
 * Conversational PRD-first page generation modal (Pages v2 — Session 1).
 *
 * Three visual states driven by session.status from the backend:
 *
 *   1. prompt — user types a description, hits Send. Backend Claude
 *      generates a PRD + sitemap.
 *   2. prd-preview — show parsed PRD (title, audience, goals,
 *      sections). User can:
 *        • Refine: opens prompt textarea again, prepended by a hint
 *          about iterating; another POST /prompt re-derives the PRD.
 *        • Approve: POST /approve flips status='approved', then
 *          immediately POST /generate to queue the worker.
 *   3. generating — poll GET /sessions/{id} every 2s. On status='complete',
 *      navigate to the generated page via onComplete callback. On
 *      'failed', show the error_message + a Try Again button.
 *
 * Closes the Bug 1 gap (page builder Generate button didn't exist).
 */
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ArrowRight, Check, Loader2, Pencil, Plus, RotateCcw, Sparkles, Trash2, X,
} from 'lucide-react'
import { pagesApi } from '@/api/pages'
import { useTranslation } from 'react-i18next'

interface SessionData {
  id: string
  status: 'drafting' | 'approved' | 'generating' | 'complete' | 'failed'
  prompt_history: { role: string; content: string; timestamp: string }[]
  prd: {
    title?: string
    site_title?: string
    audience?: string
    goals?: string[]
    locale?: string
    provider?: string
    /** Multi-page shape (post-S5.1): the AI planned a whole site. */
    pages?: {
      path: string; role?: string; title?: string; nav_label?: string
      sections?: {
        id: string; type?: string; category?: string; title?: string; summary?: string
        variant_id?: string; thumbnail_url?: string | null
        fields?: Record<string, unknown>
      }[]
    }[]
    /** Legacy single-page shape (pre-S5.1). Kept for old sessions. */
    sections?: {
      id: string; type: string; title: string; summary: string
      variant_id?: string; thumbnail_url?: string | null; fields?: Record<string, unknown>
    }[]
  } | null
  sitemap: string[]
  page_id: string | null
  error_message: string | null
}

interface Props {
  open: boolean
  onClose: () => void
  onComplete: (pageId: string) => void
}

interface SitemapPage {
  path: string
  role: string
  title: string
  nav_label: string
  purpose: string
  keep?: boolean
}
interface Sitemap {
  site_title: string
  audience: string
  recommendation: string
  pages: SitemapPage[]
}

export default function PageAIGenerateModal({ open, onClose, onComplete }: Props) {
  const { t, i18n } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [showPromptAgain, setShowPromptAgain] = useState(false)
  const [sitemap, setSitemap] = useState<Sitemap | null>(null)
  const completionFiredRef = useRef(false)

  // Auto-create a session the first time the modal opens. Resets on close.
  const createSessionMut = useMutation({
    mutationFn: () => pagesApi.aiCreateSession(),
    onSuccess: (resp: any) => {
      const id = resp?.data?.id
      if (id) setSessionId(id)
    },
    onError: () => toast.error(t('ui:PageAIGenerateModal.couldnTStartGenerationSession')),
  })
  useEffect(() => {
    if (open && !sessionId && !createSessionMut.isPending) {
      createSessionMut.mutate()
    }
    if (!open) {
      // Reset state on close
      setSessionId(null)
      setPrompt('')
      setShowPromptAgain(false)
      setSitemap(null)
      completionFiredRef.current = false
    }
    // createSessionMut intentionally omitted — mutate is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Polling: 2s while status in {generating, approved}; off otherwise.
  const sessionQuery = useQuery({
    queryKey: ['ai-page-session', sessionId],
    queryFn: () => pagesApi.aiGetSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (q) => {
      const s = (q.state.data as any)?.data as SessionData | undefined
      if (s?.status === 'generating' || s?.status === 'approved') return 2000
      return false
    },
  })
  const session = (sessionQuery.data as any)?.data as SessionData | undefined

  // Fire onComplete exactly once when status hits 'complete' with a page_id.
  useEffect(() => {
    if (
      session?.status === 'complete' &&
      session.page_id &&
      !completionFiredRef.current
    ) {
      completionFiredRef.current = true
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      onComplete(session.page_id)
    }
  }, [session?.status, session?.page_id, onComplete, queryClient])

  // Step 1: cheap sitemap suggestion. The user confirms / edits before
  // we spend fill tokens.
  const sitemapMut = useMutation({
    mutationFn: (p: string) => pagesApi.aiSuggestSitemap(sessionId!, p, i18n.language === 'fr-CA' ? 'fr-CA' : 'en') as Promise<{ data: { sitemap: Sitemap } }>,
    onSuccess: (resp) => {
      const s = resp?.data?.sitemap
      if (!s) return
      setSitemap({ ...s, pages: s.pages.map(p => ({ ...p, keep: true })) })
    },
    onError: (e: any) =>
      toast.error(t('ui:PageAIGenerateModal.sitemapFailed', { v0: e?.message || '' })),
  })

  const submitMut = useMutation({
    mutationFn: (args: { prompt: string; pages?: SitemapPage[] }) =>
      pagesApi.aiSubmitPrompt(sessionId!, args.prompt, i18n.language === 'fr-CA' ? 'fr-CA' : 'en', args.pages),
    onSuccess: (resp: any) => {
      const s = resp?.data as SessionData
      // If parse failed, the backend returns status='failed'. Show it.
      if (s?.status === 'failed') {
        toast.error(s.error_message || 'Couldn\'t parse the response. Try rephrasing.')
      }
      setPrompt('')
      setShowPromptAgain(false)
      setSitemap(null)
      queryClient.setQueryData(['ai-page-session', sessionId], { data: s })
    },
    onError: (e: any) =>
      toast.error(t('ui:PageAIGenerateModal.generationFailedV0', { v0: e?.message || '' })),
  })

  // PrdStep lets the user drop individual pages before approval. When
  // droppedPaths is non-empty, we PATCH the session's PRD to the
  // trimmed set before approving, so the generator materialises only
  // what the user actually wants.
  const [droppedPaths, setDroppedPaths] = useState<string[]>([])
  useEffect(() => {
    if (!session || session.status !== 'drafting') setDroppedPaths([])
  }, [session?.id, session?.status])

  const approveMut = useMutation({
    mutationFn: async () => {
      if (droppedPaths.length > 0) {
        await pagesApi.aiPatchPrd(sessionId!, { drop_paths: droppedPaths })
      }
      await pagesApi.aiApprovePrd(sessionId!)
      return pagesApi.aiTriggerGenerate(sessionId!)
    },
    onSuccess: () => {
      toast.success(t('ui:PageAIGenerateModal.generatingYourPage'))
      queryClient.invalidateQueries({ queryKey: ['ai-page-session', sessionId] })
    },
    onError: (e: any) =>
      toast.error(t('ui:PageAIGenerateModal.couldnTKickOffGeneration', { v0: e?.message || '' })),
  })

  if (!open) return null

  // Render dispatch — derived purely from session.status + has-prd
  const hasPrd = !!(session?.prd?.pages?.length || session?.prd?.sections?.length)
  // Clarifying-question case: the AI parsed our prompt as too vague, so
  // it returned a PRD with an `audience` field populated but no sections.
  // Previously this rendered the same blank prompt step the user just
  // submitted from, with no feedback — looked like the button did nothing.
  // Now we surface the AI's question on the PromptStep so the user can
  // see what's being asked.
  const aiClarifyingQuestion =
    session?.prd && !hasPrd && (session.prd.audience || '').trim()
      ? session.prd.audience!.trim()
      : null
  const phase: 'prompt' | 'sitemap' | 'prd' | 'working' | 'failed' =
    !session ? 'prompt'
    : session.status === 'failed' ? 'failed'
    : session.status === 'generating' || session.status === 'approved' ? 'working'
    : hasPrd && !showPromptAgain ? 'prd'
    : sitemap && !showPromptAgain ? 'sitemap'
    : 'prompt'

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-500" />
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
             {t('ui:PageAIGenerateModal.generateANewPageWith')}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {phase === 'prompt' && (
            <PromptStep
              isLoading={createSessionMut.isPending || sitemapMut.isPending || submitMut.isPending}
              isIteration={showPromptAgain}
              clarifyingQuestion={aiClarifyingQuestion}
              prompt={prompt}
              setPrompt={setPrompt}
              onSubmit={() => {
                if (prompt.trim() && sessionId) sitemapMut.mutate(prompt.trim())
              }}
              onCancel={() => setShowPromptAgain(false)}
            />
          )}

          {phase === 'sitemap' && sitemap && (
            <SitemapStep
              sitemap={sitemap}
              onChange={setSitemap}
              onBack={() => { setSitemap(null); setShowPromptAgain(false) }}
              onGenerate={() => {
                const kept = sitemap.pages.filter(p => p.keep !== false)
                if (kept.length === 0) return
                submitMut.mutate({ prompt, pages: kept })
              }}
              isGenerating={submitMut.isPending}
            />
          )}

          {phase === 'prd' && session?.prd && (
            <PrdStep
              prd={session.prd}
              droppedPaths={droppedPaths}
              onDropToggle={(path) => setDroppedPaths(prev =>
                prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path],
              )}
              onRefine={() => setShowPromptAgain(true)}
              onApprove={() => approveMut.mutate()}
              isApproving={approveMut.isPending}
            />
          )}

          {phase === 'working' && (
            <WorkingStep status={session?.status || 'approved'} />
          )}

          {phase === 'failed' && (
            <FailedStep
              errorMessage={session?.error_message ?? null}
              onTryAgain={() => {
                completionFiredRef.current = false
                setSessionId(null)
                setPrompt('')
                createSessionMut.mutate()
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function PromptStep({
  isLoading,
  isIteration,
  clarifyingQuestion,
  prompt,
  setPrompt,
  onSubmit,
  onCancel,
}: {
  isLoading: boolean
  isIteration: boolean
  clarifyingQuestion: string | null
  prompt: string
  setPrompt: (s: string) => void
  onSubmit: () => void
  onCancel: () => void
}) {
  const { t } = useTranslation('ui')
  return (
    <div className="space-y-4">
      {clarifyingQuestion ? (
        <div className="p-3 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/70 dark:bg-indigo-950/30">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-700 dark:text-indigo-300 mb-1">
           {t('ui:PageAIGenerateModal.aiNeedsABitMore')}
          </p>
          <p className="text-sm text-gray-800 dark:text-gray-100">
            {clarifyingQuestion}
          </p>
        </div>
      ) : (
        <div>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {isIteration
              ? t('ui:PageAIGenerateModal.tellAiWhatToChange')
              : t('ui:PageAIGenerateModal.describeThePageYouWant')}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
           {t('ui:PageAIGenerateModal.exampleLandingPageForA')}
          </p>
        </div>
      )}
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={isIteration ? t('ui:PageAIGenerateModal.whatShouldChange') : t('ui:PageAIGenerateModal.describeYourPage')}
        rows={6}
        maxLength={4000}
        className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
        autoFocus
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && prompt.trim()) {
            onSubmit()
          }
        }}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {prompt.length}/4000 · ⌘↵ to submit
        </span>
        <div className="flex gap-2">
          {isIteration && (
            <button
              onClick={onCancel}
              className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800"
            >
             {t('ui:PageAIGenerateModal.cancel')}
            </button>
          )}
          <button
            onClick={onSubmit}
            disabled={isLoading || !prompt.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t('ui:PageAIGenerateModal.thinking')}
              </>
            ) : (
              <>
               {t('ui:PageAIGenerateModal.generatePlan')} <ArrowRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

function SitemapStep({
  sitemap, onChange, onBack, onGenerate, isGenerating,
}: {
  sitemap: Sitemap
  onChange: (s: Sitemap) => void
  onBack: () => void
  onGenerate: () => void
  isGenerating: boolean
}) {
  const { t } = useTranslation('ui')
  const [addingPath, setAddingPath] = useState('')
  const update = (fn: (draft: Sitemap) => Sitemap) => onChange(fn(structuredClone(sitemap)))
  const togglePage = (i: number) => update(s => {
    if (i === 0) return s   // home always stays
    s.pages[i].keep = !(s.pages[i].keep ?? true)
    return s
  })
  const renameLabel = (i: number, v: string) => update(s => { s.pages[i].nav_label = v.slice(0, 24); return s })
  const addPage = () => {
    const path = addingPath.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    if (!path || sitemap.pages.some(p => p.path === path)) return
    setAddingPath('')
    update(s => {
      s.pages.push({ path, role: path, title: path[0].toUpperCase() + path.slice(1), nav_label: path[0].toUpperCase() + path.slice(1), purpose: '', keep: true })
      return s
    })
  }
  const kept = sitemap.pages.filter(p => p.keep !== false)
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 mb-1">{t('ui:PageAIGenerateModal.suggestedSitemap')}</h3>
        <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{sitemap.site_title || t('ui:PageAIGenerateModal.untitled')}</h4>
        {sitemap.audience && <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{sitemap.audience}</p>}
        {sitemap.recommendation && (
          <p className="mt-2 rounded-md bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 px-3 py-2 text-xs text-indigo-800 dark:text-indigo-200">
            <span className="font-semibold">{t('ui:PageAIGenerateModal.aiRecommends')}</span> {sitemap.recommendation}
          </p>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h5 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('ui:PageAIGenerateModal.pagesToBuild', { count: kept.length })}</h5>
          <p className="text-[11px] text-gray-400">{t('ui:PageAIGenerateModal.uncheckToSkip')}</p>
        </div>
        <ul className="space-y-1.5">
          {sitemap.pages.map((p, i) => {
            const keep = p.keep !== false
            return (
              <li key={p.path} className={`flex items-start gap-3 px-3 py-2 rounded-md border ${keep ? 'bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700' : 'bg-transparent border-dashed border-gray-300 dark:border-gray-700 opacity-60'}`}>
                <input type="checkbox" checked={keep} disabled={i === 0} onChange={() => togglePage(i)} className="mt-1 h-4 w-4 rounded border-gray-300" title={i === 0 ? t('ui:PageAIGenerateModal.homeAlwaysKept') : ''} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <input value={p.nav_label} onChange={e => renameLabel(i, e.target.value)} disabled={!keep} className="text-sm font-medium text-gray-900 dark:text-gray-100 bg-transparent border-0 border-b border-transparent focus:border-indigo-500 focus:outline-none disabled:opacity-60 min-w-0 flex-1" />
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-gray-500">/{p.path}</span>
                    {i === 0 && <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-500">{t('ui:PageAIGenerateModal.home')}</span>}
                  </div>
                  {p.purpose && <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2">{p.purpose}</p>}
                </div>
                {i > 0 && (
                  <button onClick={() => update(s => { s.pages.splice(i, 1); return s })} className="p-1 rounded text-gray-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950" aria-label={t('ui:PageAIGenerateModal.removePage')}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </li>
            )
          })}
        </ul>
        <div className="mt-2 flex items-center gap-2">
          <input value={addingPath} onChange={e => setAddingPath(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addPage() }} placeholder={t('ui:PageAIGenerateModal.addPagePlaceholder')} className="flex-1 rounded-md border border-dashed border-gray-300 dark:border-gray-600 bg-transparent px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400" />
          <button onClick={addPage} disabled={!addingPath.trim()} className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950 disabled:opacity-40"><Plus className="h-3.5 w-3.5" /> {t('ui:PageAIGenerateModal.addPage')}</button>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-800">
        <button onClick={onBack} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md">
          <Pencil className="h-3.5 w-3.5" /> {t('ui:PageAIGenerateModal.changePrompt')}
        </button>
        <button onClick={onGenerate} disabled={isGenerating || kept.length === 0} className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50">
          {isGenerating ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> {t('ui:PageAIGenerateModal.generatingPages')}</> : <>{t('ui:PageAIGenerateModal.buildTheseNPages', { count: kept.length })} <ArrowRight className="h-3.5 w-3.5" /></>}
        </button>
      </div>
    </div>
  )
}


function PrdStep({
  prd,
  droppedPaths,
  onDropToggle,
  onRefine,
  onApprove,
  isApproving,
}: {
  prd: SessionData['prd']
  droppedPaths: string[]
  onDropToggle: (path: string) => void
  onRefine: () => void
  onApprove: () => void
  isApproving: boolean
}) {
  const { t } = useTranslation('ui')
  if (!prd) return null
  // Normalise both shapes to an array of pages for rendering — legacy
  // (single-page) sessions get one synthetic Home page.
  const pages = prd.pages?.length ? prd.pages : (prd.sections?.length ? [{ path: 'home', title: prd.title || 'Home', nav_label: 'Home', sections: prd.sections }] : [])
  const dropped = new Set(droppedPaths)
  const remaining = pages.filter(p => !dropped.has(p.path))
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 mb-1">
          {pages.length > 1 ? t('ui:PageAIGenerateModal.proposedSite') : t('ui:PageAIGenerateModal.proposedPage')}
        </h3>
        <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          {prd.site_title || prd.title || t('ui:PageAIGenerateModal.untitled')}
        </h4>
        {prd.audience && (
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            <span className="font-medium text-gray-500 dark:text-gray-500">{t('ui:PageAIGenerateModal.for')} </span>
            {prd.audience}
          </p>
        )}
      </div>

      {prd.goals?.length ? (
        <div>
          <h5 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">{t('ui:PageAIGenerateModal.goals')}</h5>
          <ul className="space-y-1">
            {prd.goals.map((g, i) => (
              <li key={i} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                <span>{g}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {pages.length > 0 && (
        <div className="space-y-4">
          {pages.map((page, pi) => {
            const isDropped = dropped.has(page.path)
            const canDrop = page.path !== 'home' && pages.length > 1
            return (
            <div key={page.path || pi} className={isDropped ? 'opacity-40' : ''}>
              <div className="flex items-baseline justify-between mb-2 gap-2">
                <h5 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 flex-1 min-w-0 truncate">
                  {t('ui:PageAIGenerateModal.pageCountLabel', { title: page.title || page.path || 'Page', count: page.sections?.length ?? 0 })}
                </h5>
                {pages.length > 1 && (
                  <span className="text-[10px] uppercase tracking-wider text-gray-400">/{page.path}</span>
                )}
                {canDrop && (
                  <button
                    type="button"
                    onClick={() => onDropToggle(page.path)}
                    className={`shrink-0 p-1 rounded ${isDropped ? 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950' : 'text-gray-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950'}`}
                    aria-label={t('ui:PageAIGenerateModal.removePageFromPlan')}
                    title={t('ui:PageAIGenerateModal.removePageFromPlan')}
                  >
                    {isDropped ? <RotateCcw className="h-3.5 w-3.5" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                )}
              </div>
              <ol className="space-y-1.5">
                {(page.sections || []).map((s, i) => {
                  const f = s.fields || {}
                  const headline = [f.HEADLINE, f.TITLE_1, f.BRAND_NAME, f.TEXT].find(v => typeof v === 'string' && v) as string | undefined
                  const sub = [f.SUBHEADLINE, f.TEXT_1, f.SUBMIT_TEXT].find(v => typeof v === 'string' && v) as string | undefined
                  return (
                    <li key={s.id || `${page.path}-${i}`} className="flex items-start gap-3 px-3 py-2 rounded-md bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
                      <span className="text-xs font-mono text-gray-400 dark:text-gray-500 mt-0.5 shrink-0">{i + 1}.</span>
                      {s.thumbnail_url && (
                        <img src={s.thumbnail_url} alt="" className="w-24 aspect-[16/10] object-cover object-top rounded border border-gray-200 dark:border-gray-700 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2">
                          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{s.title}</span>
                          <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-gray-500">{s.type || (s as { category?: string }).category}</span>
                        </div>
                        {headline ? <p className="text-xs text-gray-800 dark:text-gray-200 mt-0.5 font-medium truncate">“{headline}”</p> : null}
                        {(sub || s.summary) && <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2">{sub || s.summary}</p>}
                      </div>
                    </li>
                  )
                })}
              </ol>
            </div>
            )
          })}
          <p className="text-[11px] text-gray-400">{t('ui:PageAIGenerateModal.copyOnlyNote')}</p>
          {droppedPaths.length > 0 && (
            <p className="text-[11px] text-rose-600 dark:text-rose-300">{t('ui:PageAIGenerateModal.pagesToBuild', { count: remaining.length })}</p>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-800">
        <button
          onClick={onRefine}
          disabled={isApproving}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md"
        >
          <Pencil className="h-3.5 w-3.5" /> {t('ui:PageAIGenerateModal.refinePlan')}
        </button>
        <button
          onClick={onApprove}
          disabled={isApproving}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
        >
          {isApproving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t('ui:PageAIGenerateModal.queueing')}
            </>
          ) : (
            <>
             {t('ui:PageAIGenerateModal.approveGenerate')} <Sparkles className="h-3.5 w-3.5" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}

function WorkingStep({ status }: { status: string }) {
  const { t } = useTranslation('ui')
  return (
    <div className="py-12 text-center space-y-4">
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-800">
        <Sparkles className="h-6 w-6 text-indigo-500 animate-pulse" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
          {status === 'approved' ? t('ui:PageAIGenerateModal.queued') : t('ui:PageAIGenerateModal.generatingSections')}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:PageAIGenerateModal.thisUsuallyTakes3060')}
        </p>
      </div>
    </div>
  )
}

function FailedStep({
  errorMessage,
  onTryAgain,
}: {
  errorMessage: string | null
  onTryAgain: () => void
}) {
  const { t } = useTranslation('ui')
  return (
    <div className="py-8 text-center space-y-4">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800">
        <X className="h-5 w-5 text-red-500" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
         {t('ui:PageAIGenerateModal.generationFailed')}
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
          {errorMessage || t('ui:PageAIGenerateModal.somethingWentWrongTryRephrasing')}
        </p>
      </div>
      <button
        onClick={onTryAgain}
        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
      >
        <RotateCcw className="h-3.5 w-3.5" /> {t('ui:PageAIGenerateModal.tryAgain')}
      </button>
    </div>
  )
}
