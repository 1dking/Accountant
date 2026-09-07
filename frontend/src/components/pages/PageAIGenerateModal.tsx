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
  ArrowRight, Check, Loader2, Pencil, RotateCcw, Sparkles, X,
} from 'lucide-react'
import { pagesApi } from '@/api/pages'
import { useTranslation } from 'react-i18next'

interface SessionData {
  id: string
  status: 'drafting' | 'approved' | 'generating' | 'complete' | 'failed'
  prompt_history: { role: string; content: string; timestamp: string }[]
  prd: {
    title?: string
    audience?: string
    goals?: string[]
    locale?: string
    provider?: string
    sections?: {
      id: string; type: string; title: string; summary: string
      /** Block model v2 plan: chosen library block + the copy the AI wrote. */
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

export default function PageAIGenerateModal({ open, onClose, onComplete }: Props) {
  const { t, i18n } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [showPromptAgain, setShowPromptAgain] = useState(false)
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

  const submitMut = useMutation({
    mutationFn: (p: string) => pagesApi.aiSubmitPrompt(sessionId!, p, i18n.language === 'fr-CA' ? 'fr-CA' : 'en'),
    onSuccess: (resp: any) => {
      const s = resp?.data as SessionData
      // If parse failed, the backend returns status='failed'. Show it.
      if (s?.status === 'failed') {
        toast.error(s.error_message || 'Couldn\'t parse the response. Try rephrasing.')
      }
      setPrompt('')
      setShowPromptAgain(false)
      queryClient.setQueryData(['ai-page-session', sessionId], { data: s })
    },
    onError: (e: any) =>
      toast.error(t('ui:PageAIGenerateModal.generationFailedV0', { v0: e?.message || '' })),
  })

  const approveMut = useMutation({
    mutationFn: async () => {
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
  const hasPrd = !!session?.prd?.sections?.length
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
  const phase: 'prompt' | 'prd' | 'working' | 'failed' =
    !session ? 'prompt'
    : session.status === 'failed' ? 'failed'
    : session.status === 'generating' || session.status === 'approved' ? 'working'
    : hasPrd && !showPromptAgain ? 'prd'
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
              isLoading={createSessionMut.isPending || submitMut.isPending}
              isIteration={showPromptAgain}
              clarifyingQuestion={aiClarifyingQuestion}
              prompt={prompt}
              setPrompt={setPrompt}
              onSubmit={() => {
                if (prompt.trim() && sessionId) submitMut.mutate(prompt.trim())
              }}
              onCancel={() => setShowPromptAgain(false)}
            />
          )}

          {phase === 'prd' && session?.prd && (
            <PrdStep
              prd={session.prd}
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

function PrdStep({
  prd,
  onRefine,
  onApprove,
  isApproving,
}: {
  prd: SessionData['prd']
  onRefine: () => void
  onApprove: () => void
  isApproving: boolean
}) {
  const { t } = useTranslation('ui')
  if (!prd) return null
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 mb-1">
         {t('ui:PageAIGenerateModal.proposedPage')}
        </h3>
        <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          {prd.title || t('ui:PageAIGenerateModal.untitled')}
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
          <h5 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
           {t('ui:PageAIGenerateModal.goals')}
          </h5>
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

      {prd.sections?.length ? (
        <div>
          <h5 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
           {t('ui:PageAIGenerateModal.sections')}{prd.sections.length})
          </h5>
          <ol className="space-y-1.5">
            {prd.sections.map((s, i) => {
              const f = s.fields || {}
              const headline = [f.HEADLINE, f.TITLE_1, f.BRAND_NAME, f.TEXT].find(v => typeof v === 'string' && v) as string | undefined
              const sub = [f.SUBHEADLINE, f.TEXT_1, f.SUBMIT_TEXT].find(v => typeof v === 'string' && v) as string | undefined
              return (
              <li
                key={s.id || i}
                className="flex items-start gap-3 px-3 py-2 rounded-md bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700"
              >
                <span className="text-xs font-mono text-gray-400 dark:text-gray-500 mt-0.5 shrink-0">
                  {i + 1}.
                </span>
                {s.thumbnail_url && (
                  <img src={s.thumbnail_url} alt="" className="w-24 aspect-[16/10] object-cover object-top rounded border border-gray-200 dark:border-gray-700 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {s.title}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-gray-500">
                      {s.type}
                    </span>
                  </div>
                  {headline ? (
                    <p className="text-xs text-gray-800 dark:text-gray-200 mt-0.5 font-medium truncate">“{headline}”</p>
                  ) : null}
                  {(sub || s.summary) && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {sub || s.summary}
                    </p>
                  )}
                </div>
              </li>
              )
            })}
          </ol>
          <p className="mt-2 text-[11px] text-gray-400">{t('ui:PageAIGenerateModal.copyOnlyNote')}</p>
        </div>
      ) : null}

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
