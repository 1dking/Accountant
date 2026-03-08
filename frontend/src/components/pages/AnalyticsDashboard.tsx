import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { pagesApi } from '@/api/pages'
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  X,
  Eye,
  Users,
  Clock,
  TrendingDown,
  Target,
  Loader2,
} from 'lucide-react'

interface AnalyticsDashboardProps {
  pageId: string
  onClose: () => void
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316']

const DAY_OPTIONS = [
  { label: '7 days', value: 7 },
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
]

function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

export default function AnalyticsDashboard({ pageId, onClose }: AnalyticsDashboardProps) {
  const [days, setDays] = useState(30)

  const { data: res, isLoading } = useQuery({
    queryKey: ['page-analytics', pageId, days],
    queryFn: () => pagesApi.getAnalytics(pageId, days),
  })

  const analytics = (res as any)?.data?.data

  const viewsByDay = analytics?.views_by_day ?? []
  const topSources = analytics?.top_sources ?? []
  const devices = analytics?.devices ?? {}
  const scrollDepth = analytics?.scroll_depth ?? {}
  const topClicks = analytics?.top_clicks ?? []
  const utmCampaigns = analytics?.utm_campaigns ?? []

  const deviceData = Object.entries(devices).map(([name, value]) => ({
    name,
    value: value as number,
  }))

  const scrollData = Object.entries(scrollDepth).map(([depth, count]) => ({
    depth,
    count: count as number,
  }))

  const sourceData = topSources.map((s: { source: string; count: number }) => ({
    name: s.source,
    value: s.count,
  }))

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="w-full max-w-6xl my-8 bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Page Analytics</h2>
          <div className="flex items-center gap-3">
            <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
              {DAY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDays(opt.value)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    days === opt.value
                      ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">Loading analytics...</span>
          </div>
        ) : !analytics ? (
          <div className="flex items-center justify-center py-20 text-sm text-gray-500 dark:text-gray-400">
            No analytics data available yet.
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              <MetricCard
                icon={<Eye className="w-4 h-4" />}
                label="Total Visitors"
                value={analytics.total_views?.toLocaleString() ?? '0'}
                color="blue"
              />
              <MetricCard
                icon={<Users className="w-4 h-4" />}
                label="Unique Visitors"
                value={analytics.unique_visitors?.toLocaleString() ?? '0'}
                color="green"
              />
              <MetricCard
                icon={<Clock className="w-4 h-4" />}
                label="Avg Time on Page"
                value={formatSeconds(analytics.avg_time_seconds ?? 0)}
                color="amber"
              />
              <MetricCard
                icon={<TrendingDown className="w-4 h-4" />}
                label="Bounce Rate"
                value={`${((analytics.bounce_rate ?? 0) * 100).toFixed(1)}%`}
                color="red"
              />
              <MetricCard
                icon={<Target className="w-4 h-4" />}
                label="Conversion Rate"
                value={`${((analytics.conversion_rate ?? 0) * 100).toFixed(1)}%`}
                color="purple"
              />
            </div>

            {/* Visitors Over Time */}
            {viewsByDay.length > 0 && (
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">Visitors Over Time</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={viewsByDay}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: '#9ca3af' }}
                      tickFormatter={(d: string) => {
                        const date = new Date(d)
                        return `${date.getMonth() + 1}/${date.getDate()}`
                      }}
                    />
                    <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                        fontSize: 12,
                        color: '#f3f4f6',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="views"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      name="Total Views"
                    />
                    <Line
                      type="monotone"
                      dataKey="unique"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                      name="Unique"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Pie Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Traffic Sources */}
              {sourceData.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">Traffic Sources</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={sourceData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="value"
                        label={((props: Record<string, any>) => `${props.name ?? ''} ${((props.percent ?? 0) * 100).toFixed(0)}%`) as any}
                      >
                        {sourceData.map((_: unknown, i: number) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Devices */}
              {deviceData.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">Devices</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={deviceData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="value"
                        label={((props: Record<string, any>) => `${props.name ?? ''} ${((props.percent ?? 0) * 100).toFixed(0)}%`) as any}
                      >
                        {deviceData.map((_: unknown, i: number) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Scroll Depth Bar Chart */}
            {scrollData.length > 0 && (
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">Scroll Depth</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={scrollData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="depth" tick={{ fontSize: 12, fill: '#9ca3af' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                        fontSize: 12,
                        color: '#f3f4f6',
                      }}
                    />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Visitors" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Tables Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Top Clicks */}
              {topClicks.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Top Clicks</h3>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800">
                        <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Element</th>
                        <th className="text-right px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Clicks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topClicks.map((click: { element: string; count: number }, i: number) => (
                        <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 last:border-0">
                          <td className="px-4 py-2.5 text-gray-900 dark:text-gray-100 truncate max-w-[200px]">
                            {click.element}
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400 font-mono">
                            {click.count.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* UTM Campaigns */}
              {utmCampaigns.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">UTM Campaigns</h3>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800">
                        <th className="text-left px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Campaign</th>
                        <th className="text-right px-4 py-2 text-gray-500 dark:text-gray-400 font-medium">Visitors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {utmCampaigns.map((utm: { campaign: string; visitors: number }, i: number) => (
                        <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 last:border-0">
                          <td className="px-4 py-2.5 text-gray-900 dark:text-gray-100 truncate max-w-[200px]">
                            {utm.campaign}
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400 font-mono">
                            {utm.visitors.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---- Metric Card Sub-component ---- */

const colorMap: Record<string, string> = {
  blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
  green: 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400',
  amber: 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  red: 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400',
  purple: 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
}

function MetricCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string
  color: string
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
      <div className={`inline-flex p-2 rounded-lg mb-2 ${colorMap[color] ?? colorMap.blue}`}>
        {icon}
      </div>
      <div className="text-xl font-bold text-gray-900 dark:text-gray-100">{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}
