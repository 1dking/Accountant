import { useQuery } from '@tanstack/react-query'
import { listActivity } from '@/api/collaboration'
import { getInitials, formatRelativeTime } from '@/lib/utils'
import type { ActivityLogEntry } from '@/types/models'

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-green-100 text-green-700',
  upload: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700',
  update: 'bg-amber-100 text-amber-700',
  delete: 'bg-red-100 text-red-700',
  approve: 'bg-emerald-100 text-emerald-700',
  reject: 'bg-red-100 text-red-700',
  comment: 'bg-purple-100 text-purple-700',
}

function getActionColor(action: string): string {
  const key = Object.keys(ACTION_COLORS).find((k) => action.toLowerCase().includes(k))
  return key ? ACTION_COLORS[key] : 'bg-gray-100 dark:bg-gray-800 text-gray-700'
}

function ActivityEntry({ entry }: { entry: ActivityLogEntry }) {
  const colorClass = getActionColor(entry.action)

  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div
        className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-medium shrink-0 ${colorClass}`}
      >
        {getInitials(entry.user_name)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-gray-900 dark:text-gray-100">
          <span className="font-medium">{entry.user_name || 'Unknown'}</span>{' '}
          <span className="text-gray-600 dark:text-gray-400">
            {entry.action} {entry.resource_type}
          </span>
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          {formatRelativeTime(entry.created_at)}
        </p>
      </div>
    </div>
  )
}

export default function ActivityPanel() {
  const { data } = useQuery({
    queryKey: ['activity', { page_size: 20 }],
    queryFn: () => listActivity({ page_size: 20 }),
  })

  const activities: ActivityLogEntry[] = data?.data ?? []

  return (
    <aside className="hidden xl:flex w-80 border-l border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-900 flex-col">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Activity</h2>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {activities.length === 0 ? (
          <p className="p-4 text-sm text-gray-400 dark:text-gray-500 text-center">No recent activity</p>
        ) : (
          <div className="divide-y divide-gray-50 dark:divide-gray-800">
            {activities.map((entry) => (
              <ActivityEntry key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
