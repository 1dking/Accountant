import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles, RefreshCw, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { getContactBrief, regenerateContactBrief } from '@/api/automation'

function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diffMs = Date.now() - t
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  return `${day}d ago`
}

export default function ContactAIBrief({ contactId }: { contactId: string }) {
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['contact-brief', contactId],
    queryFn: () => getContactBrief(contactId),
    enabled: !!contactId,
    staleTime: 60_000, // re-fetch at most once a minute
  })

  const regenMut = useMutation({
    mutationFn: () => regenerateContactBrief(contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-brief', contactId] })
      toast.success('Brief refreshed')
    },
    onError: (e: any) => toast.error(`Brief refresh failed: ${e.message || ''}`),
  })

  const brief = data?.data?.brief
  const generated = data?.data?.generated_at
  const isFresh = data?.data?.is_fresh

  return (
    <div className="mx-6 mt-4 bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <Sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
              Brief
            </h3>
            <button
              onClick={() => regenMut.mutate()}
              disabled={regenMut.isPending}
              className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 disabled:opacity-50"
              title="Regenerate brief"
            >
              {regenMut.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
          {isLoading ? (
            <div className="text-sm text-indigo-600 dark:text-indigo-300 flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              Generating brief…
            </div>
          ) : isError ? (
            <div className="text-sm text-red-600 dark:text-red-400">
              Brief unavailable. Try refresh.
            </div>
          ) : !brief ? (
            <div className="text-sm text-indigo-600 dark:text-indigo-300">
              No brief yet. Add a memory or message to generate context.
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                {brief}
              </p>
              {generated && (
                <div className="text-[10px] text-indigo-500 dark:text-indigo-400 mt-1">
                  {isFresh ? 'Generated' : 'Cached'} {relativeTime(generated)}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
