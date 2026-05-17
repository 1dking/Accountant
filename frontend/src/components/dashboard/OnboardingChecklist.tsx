import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Check, X, ChevronRight, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import {
  getOnboarding,
  dismissOnboardingItem,
  type OnboardingItem,
} from '@/api/auth'

export default function OnboardingChecklist() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['onboarding'],
    queryFn: () => getOnboarding(),
    staleTime: 30_000,
  })

  const dismissMut = useMutation({
    mutationFn: dismissOnboardingItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding'] })
    },
    onError: (e: any) => toast.error(`Dismiss failed: ${e.message || ''}`),
  })

  if (isLoading || !data?.data) return null

  const { items, overall_progress } = data.data
  // Hide live items (not dismissed) — when everything's done or dismissed,
  // the card disappears from the dashboard entirely.
  const live = items.filter((i) => !i.dismissed_at)
  const incomplete = live.filter((i) => !i.completed)
  if (incomplete.length === 0) return null

  const completedCount = live.filter((i) => i.completed).length
  const totalCount = live.length

  const handleClick = (item: OnboardingItem) => {
    if (item.action_link) navigate(item.action_link)
  }

  return (
    <section className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 border border-indigo-200 dark:border-indigo-800 rounded-xl p-5 mb-6">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">
              Set up your account
            </h2>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
              {completedCount} of {totalCount} done ({Math.round(overall_progress * 100)}%)
            </p>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-indigo-100 dark:bg-indigo-900/30 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all"
          style={{ width: `${overall_progress * 100}%` }}
        />
      </div>

      {/* Items */}
      <ul className="space-y-2">
        {live.map((item) => (
          <li
            key={item.key}
            className={`group flex items-start gap-3 p-3 rounded-lg transition-colors ${
              item.completed
                ? 'bg-white/40 dark:bg-gray-900/40'
                : 'bg-white dark:bg-gray-900 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 cursor-pointer'
            }`}
            onClick={() => !item.completed && handleClick(item)}
          >
            <div
              className={`mt-0.5 h-5 w-5 rounded-full border-2 flex items-center justify-center shrink-0 ${
                item.completed
                  ? 'bg-green-500 border-green-500'
                  : 'border-gray-300 dark:border-gray-600'
              }`}
            >
              {item.completed && <Check className="h-3 w-3 text-white" />}
            </div>
            <div className="flex-1 min-w-0">
              <div
                className={`text-sm font-medium ${
                  item.completed
                    ? 'text-gray-500 dark:text-gray-400 line-through'
                    : 'text-gray-900 dark:text-gray-100'
                }`}
              >
                {item.label}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {item.description}
              </div>
            </div>
            {!item.completed && (
              <div className="flex items-center gap-1 shrink-0">
                <ChevronRight className="h-4 w-4 text-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                {item.can_dismiss && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      dismissMut.mutate(item.key)
                    }}
                    className="p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Skip this step"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
