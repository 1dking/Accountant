import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Mail, RefreshCw, Sparkles } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import {
  getEmailAbsorptionRun,
  listEmailAbsorptionRuns,
  triggerEmailAbsorption,
  type EmailAbsorptionRun,
} from '@/api/communication'
import { useTranslation } from 'react-i18next'

/**
 * Settings → Email Absorption.
 *
 * Trigger a backfill, poll the live run's progress, and surface stats
 * from past runs. The trigger endpoint creates a queued run and
 * schedules the worker via FastAPI BackgroundTasks; we poll
 * GET /email-absorb/runs/{id} every 2s while status is queued or
 * running, then stop and refresh the runs list.
 */
export default function EmailAbsorptionSettings() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [lookbackDays, setLookbackDays] = useState(90)
  const pollTimerRef = useRef<number | null>(null)

  const runsQuery = useQuery({
    queryKey: ['email-absorption-runs'],
    queryFn: listEmailAbsorptionRuns,
    refetchInterval: activeRunId ? false : 60_000,
  })

  // Live polling for the active run. Stops itself the moment status
  // transitions to complete or failed.
  const activeRunQuery = useQuery({
    queryKey: ['email-absorption-run', activeRunId],
    queryFn: () => getEmailAbsorptionRun(activeRunId!),
    enabled: !!activeRunId,
    refetchInterval: 2000,
  })

  const activeRun = activeRunQuery.data?.data
  const runsList: EmailAbsorptionRun[] = runsQuery.data?.data || []

  // Clear active-run polling once status settles. Surface a toast +
  // refresh the runs list so the historical view picks it up.
  useEffect(() => {
    if (!activeRun) return
    if (activeRun.status === 'complete' || activeRun.status === 'failed') {
      if (pollTimerRef.current) {
        window.clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
      const wasRunId = activeRunId
      setActiveRunId(null)
      queryClient.invalidateQueries({ queryKey: ['email-absorption-runs'] })
      if (activeRun.status === 'complete') {
        toast.success(
          `Absorbed ${activeRun.absorbed} email${activeRun.absorbed === 1 ? '' : 's'} ` +
            `across ${activeRun.contacts_touched} contact${activeRun.contacts_touched === 1 ? '' : 's'}`,
        )
      } else {
        toast.error(t('ui:EmailAbsorptionSettings.absorptionFailedV0', { v0: activeRun.error_message || 'unknown error' }))
      }
      // Touch the param so the linter doesn't flag wasRunId as unused.
      void wasRunId
    }
  }, [activeRun, activeRunId, queryClient])

  const triggerMut = useMutation({
    mutationFn: () => triggerEmailAbsorption(lookbackDays),
    onSuccess: (resp) => {
      const runId = resp.data?.run_id
      if (runId) {
        setActiveRunId(runId)
        toast.success(t('ui:EmailAbsorptionSettings.absorptionStartedScanningTheLast', { lookbackDays }))
      }
    },
    onError: (e: any) => toast.error(t('ui:EmailAbsorptionSettings.triggerFailedV0', { v0: e.message || '' })),
  })

  const latestRun = runsList[0]
  const lastFinished = latestRun?.finished_at || null

  return (
    <div className="space-y-4">
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start gap-3 mb-4">
          <Mail className="h-5 w-5 text-indigo-500 mt-0.5" />
          <div>
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">
             {t('ui:EmailAbsorptionSettings.emailAbsorption')}
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 max-w-2xl">
             {t('ui:EmailAbsorptionSettings.scansYourConnectedGmailAnd')}
            </p>
          </div>
        </div>

        {/* Active run progress card */}
        {activeRun && (activeRun.status === 'queued' || activeRun.status === 'running') && (
          <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-md p-4 mb-4">
            <div className="flex items-center gap-2 text-sm font-medium text-indigo-700 dark:text-indigo-300">
              <Sparkles className="h-4 w-4 animate-pulse" />
              {activeRun.status === 'queued' ? t('ui:EmailAbsorptionSettings.queued') : t('ui:EmailAbsorptionSettings.running')}
            </div>
            <div className="grid grid-cols-4 gap-3 mt-3 text-xs">
              <Stat label={t('ui:EmailAbsorptionSettings.scanned')} value={activeRun.scanned} />
              <Stat label={t('ui:EmailAbsorptionSettings.matched')} value={activeRun.matched} />
              <Stat label={t('ui:EmailAbsorptionSettings.absorbed_2')} value={activeRun.absorbed} />
              <Stat label={t('ui:EmailAbsorptionSettings.contacts_2')} value={activeRun.contacts_touched} />
            </div>
          </div>
        )}

        {/* Backfill controls */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-700 dark:text-gray-300">
             {t('ui:EmailAbsorptionSettings.lookbackDays')}
            </label>
            <input
              type="number"
              min={1}
              max={365}
              value={lookbackDays}
              onChange={(e) =>
                setLookbackDays(Math.max(1, Math.min(365, parseInt(e.target.value) || 7)))
              }
              className="w-24 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            />
            <button
              type="button"
              onClick={() => triggerMut.mutate()}
              disabled={triggerMut.isPending || !!activeRunId}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  triggerMut.isPending || activeRunId ? 'animate-spin' : ''
                }`}
              />
              {activeRunId
                ? t('ui:EmailAbsorptionSettings.runInProgress')
                : triggerMut.isPending
                  ? t('ui:EmailAbsorptionSettings.starting')
                  : t('ui:EmailAbsorptionSettings.absorbNow')}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
           {t('ui:EmailAbsorptionSettings.firstRunDoesAFull')} <strong>{t('ui:EmailAbsorptionSettings.settingsGmail')}</strong>.
          </p>
        </div>

        {/* History */}
        <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
             {t('ui:EmailAbsorptionSettings.recentRuns')}
            </h3>
            {lastFinished && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
               {t('ui:EmailAbsorptionSettings.lastFinished')} {formatRelativeTime(lastFinished)}
              </span>
            )}
          </div>
          {runsList.length === 0 ? (
            <p className="text-xs text-gray-500 dark:text-gray-400 italic">
             {t('ui:EmailAbsorptionSettings.noRunsYetClickAbsorb')}
            </p>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {runsList.map((r) => (
                <li key={r.run_id} className="py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={r.status} />
                      <span className="text-gray-600 dark:text-gray-300">
                        {r.lookback_days}{t('ui:EmailAbsorptionSettings.dLookback')}
                      </span>
                      <span className="text-gray-400 dark:text-gray-500">·</span>
                      <span className="text-gray-500 dark:text-gray-400">
                        {r.absorbed} {t('ui:EmailAbsorptionSettings.absorbed')} {r.contacts_touched} {t('ui:EmailAbsorptionSettings.contacts')} {r.scanned} scanned
                      </span>
                    </div>
                    <span className="text-gray-400 dark:text-gray-500">
                      {r.created_at ? formatRelativeTime(r.created_at) : ''}
                    </span>
                  </div>
                  {r.status === 'failed' && r.error_message && (
                    <p className="text-red-600 dark:text-red-400 mt-0.5 truncate" title={r.error_message}>
                      {r.error_message}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-indigo-500 dark:text-indigo-400">
        {label}
      </div>
      <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
        {value}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    queued: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    running: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    complete: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    failed: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  }
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide ${
        map[status] || map.queued
      }`}
    >
      {status}
    </span>
  )
}
