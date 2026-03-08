import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Lightbulb, TrendingUp, AlertTriangle, CheckCircle2,
  BarChart3, Target, Loader2, ArrowUp, ArrowDown,
  Minus, RefreshCw, Bell, Eye, MessageSquare, DollarSign,
  Calendar, Users, FileSignature,
} from 'lucide-react'
import { toast } from 'sonner'
import { coachApi } from '@/api/coach'

/* ── Health Score Gauge ────────────────────────────────────────────────── */

function HealthGauge({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 70
  const progress = (score / 100) * circumference
  const color = score >= 70 ? '#22c55e' : score >= 40 ? '#eab308' : '#ef4444'

  return (
    <div className="relative w-44 h-44 mx-auto">
      <svg viewBox="0 0 160 160" className="w-full h-full -rotate-90">
        <circle cx="80" cy="80" r="70" fill="none" stroke="currentColor" strokeWidth="10"
          className="text-gray-100 dark:text-gray-800" />
        <circle cx="80" cy="80" r="70" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          strokeLinecap="round" className="transition-all duration-1000 ease-out" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-bold text-gray-900 dark:text-gray-100">{score}</span>
        <span className="text-xs text-gray-500 dark:text-gray-400">Health Score</span>
      </div>
    </div>
  )
}

/* ── Trend Mini Chart ──────────────────────────────────────────────────── */

function TrendChart({ data, labels, color = '#f59e0b' }: { data: number[]; labels: string[]; color?: string }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data, 1)
  const points = data.map((v, i) => {
    const x = (i / Math.max(data.length - 1, 1)) * 200
    const y = 60 - (v / max) * 55
    return `${x},${y}`
  }).join(' ')

  return (
    <div className="w-full">
      <svg viewBox="0 0 200 65" className="w-full h-16">
        <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
        {data.map((v, i) => {
          const x = (i / Math.max(data.length - 1, 1)) * 200
          const y = 60 - (v / max) * 55
          return <circle key={i} cx={x} cy={y} r="3" fill={color} />
        })}
      </svg>
      <div className="flex justify-between text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
        {labels.map((l, i) => <span key={i}>{l}</span>)}
      </div>
    </div>
  )
}

/* ── Metric Card ───────────────────────────────────────────────────────── */

function MetricCard({ label, value, icon: Icon, trend, color = 'text-gray-600' }: {
  label: string; value: string | number; icon: any; trend?: 'up' | 'down' | 'flat'; color?: string
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <Icon className={`h-5 w-5 ${color}`} />
        {trend === 'up' && <ArrowUp className="h-4 w-4 text-green-500" />}
        {trend === 'down' && <ArrowDown className="h-4 w-4 text-red-500" />}
        {trend === 'flat' && <Minus className="h-4 w-4 text-gray-400" />}
      </div>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

/* ── Nudge Card ────────────────────────────────────────────────────────── */

function NudgeCard({ nudge, onRead, onActed }: {
  nudge: any
  onRead: (id: string) => void
  onActed: (id: string) => void
}) {
  const typeConfig: Record<string, { bg: string; icon: any }> = {
    meeting_followup: { bg: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800', icon: Calendar },
    proposal_followup: { bg: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800', icon: FileSignature },
    overdue_invoice: { bg: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800', icon: DollarSign },
    weekly_digest: { bg: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800', icon: BarChart3 },
    deal_insight: { bg: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800', icon: TrendingUp },
  }
  const cfg = typeConfig[nudge.nudge_type] || typeConfig.deal_insight
  const Icon = cfg.icon

  return (
    <div className={`rounded-lg border p-3 ${cfg.bg} ${nudge.is_read ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-3">
        <Icon className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{nudge.title}</p>
          <p className="text-xs text-gray-600 dark:text-gray-300 mt-0.5">{nudge.message}</p>
          <div className="flex items-center gap-2 mt-2">
            {!nudge.is_read && (
              <button onClick={() => onRead(nudge.id)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
                <Eye className="h-3 w-3" /> Mark read
              </button>
            )}
            {!nudge.is_acted_on && (
              <button onClick={() => onActed(nudge.id)} className="text-xs text-green-600 dark:text-green-400 hover:underline flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Done
              </button>
            )}
            <span className="text-[10px] text-gray-400 dark:text-gray-500 ml-auto">
              {nudge.created_at ? new Date(nudge.created_at).toLocaleDateString() : ''}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Main Intelligence Page ────────────────────────────────────────────── */

export default function IntelligencePage() {
  const queryClient = useQueryClient()
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null)

  // Fetch reports list
  const { data: reportsData, isLoading: reportsLoading } = useQuery<any>({
    queryKey: ['coach-reports'],
    queryFn: () => coachApi.listReports(),
  })

  // Fetch selected or latest report
  const reports = reportsData?.data || []
  const latestMonth = reports[0]?.report_month || null
  const activeMonth = selectedMonth || latestMonth

  const { data: reportData, isLoading: reportLoading } = useQuery<any>({
    queryKey: ['coach-report', activeMonth],
    queryFn: () => coachApi.getReport(activeMonth!),
    enabled: !!activeMonth,
  })

  // Deals summary
  const { data: dealsData } = useQuery<any>({
    queryKey: ['coach-deals-summary'],
    queryFn: () => coachApi.getDealsSummary(),
  })

  // Nudges
  const { data: nudgesData } = useQuery<any>({
    queryKey: ['coach-nudges'],
    queryFn: () => coachApi.listNudges(),
  })

  // Generate report mutation
  const generateMut = useMutation({
    mutationFn: (month?: string) => coachApi.generateReport(month),
    onSuccess: () => {
      toast.success('Intelligence report generated')
      queryClient.invalidateQueries({ queryKey: ['coach-reports'] })
      queryClient.invalidateQueries({ queryKey: ['coach-report'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Failed to generate report'),
  })

  const markReadMut = useMutation({
    mutationFn: (id: string) => coachApi.markNudgeRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['coach-nudges'] }),
  })

  const markActedMut = useMutation({
    mutationFn: (id: string) => coachApi.markNudgeActed(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['coach-nudges'] }),
  })

  const report = reportData?.data
  const deals = dealsData?.data
  const nudges = nudgesData?.data || []
  const unreadNudges = nudges.filter((n: any) => !n.is_read)

  return (
    <div className="p-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
            <Lightbulb className="h-6 w-6 text-amber-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">O-Brain Coach</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Monthly Intelligence Report</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Month selector */}
          {reports.length > 0 && (
            <select
              value={activeMonth || ''}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            >
              {reports.map((r: any) => (
                <option key={r.report_month} value={r.report_month}>{r.report_month}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => generateMut.mutate(undefined)}
            disabled={generateMut.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            {generateMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {generateMut.isPending ? 'Generating...' : 'Generate Report'}
          </button>
        </div>
      </div>

      {/* Coaching Nudges Banner */}
      {unreadNudges.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="h-4 w-4 text-amber-500" />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Coaching Nudges ({unreadNudges.length} new)</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {unreadNudges.slice(0, 4).map((n: any) => (
              <NudgeCard key={n.id} nudge={n} onRead={(id) => markReadMut.mutate(id)} onActed={(id) => markActedMut.mutate(id)} />
            ))}
          </div>
        </div>
      )}

      {reportsLoading || reportLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
        </div>
      ) : !report ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
          <Lightbulb className="h-12 w-12 text-amber-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">No Reports Yet</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Click "Generate Report" to create your first monthly intelligence report.
            Reports are also generated automatically on the 1st of each month.
          </p>
          <button
            onClick={() => generateMut.mutate(undefined)}
            disabled={generateMut.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50"
          >
            {generateMut.isPending ? 'Generating...' : 'Generate First Report'}
          </button>
        </div>
      ) : (
        <>
          {/* Health Score + Executive Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-6 flex flex-col items-center justify-center">
              <HealthGauge score={report.health_score} />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                {report.health_score >= 70 ? 'Strong momentum' : report.health_score >= 40 ? 'Room for improvement' : 'Needs attention'}
              </p>
            </div>
            <div className="lg:col-span-2 bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-6">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-amber-500" />
                Executive Summary
              </h2>
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{report.executive_summary}</p>

              {/* Quick revenue metrics */}
              {report.revenue_insights && typeof report.revenue_insights === 'object' && (
                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800 grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Revenue</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                      ${((report.revenue_insights as any).total_income || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Expenses</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-gray-100">
                      ${((report.revenue_insights as any).total_expenses || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Net</p>
                    <p className={`text-lg font-bold ${((report.revenue_insights as any).net || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ${((report.revenue_insights as any).net || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* What's Working + Watch Out */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* What's Working */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-green-200 dark:border-green-800 p-5">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                What's Working
              </h2>
              {(report.whats_working || []).length === 0 ? (
                <p className="text-sm text-gray-400">No insights available</p>
              ) : (
                <div className="space-y-3">
                  {(report.whats_working as any[]).map((item, idx) => (
                    <div key={idx} className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{item.title}</p>
                        {item.metric && <span className="text-xs font-bold text-green-600 dark:text-green-400">{item.metric}</span>}
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{item.detail}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Watch Out */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-red-200 dark:border-red-800 p-5">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                Watch Out
              </h2>
              {(report.watch_out || []).length === 0 ? (
                <p className="text-sm text-gray-400">No concerns flagged</p>
              ) : (
                <div className="space-y-3">
                  {(report.watch_out as any[]).map((item, idx) => (
                    <div key={idx} className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 flex-1">{item.title}</p>
                        <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${
                          item.severity === 'high' ? 'bg-red-100 text-red-700' : item.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                        }`}>{item.severity}</span>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{item.detail}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recommendations */}
          {(report.recommendations || []).length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-amber-200 dark:border-amber-800 p-5 mb-6">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500" />
                Coach Recommendations
              </h2>
              <div className="space-y-2">
                {(report.recommendations as any[]).map((rec, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium mt-0.5 ${
                      rec.priority === 'high' ? 'bg-red-100 text-red-700' : rec.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                    }`}>{rec.priority}</span>
                    <div>
                      <p className="text-sm text-gray-800 dark:text-gray-200">{rec.action}</p>
                      {rec.category && <span className="text-[10px] text-amber-600 dark:text-amber-400 capitalize">{rec.category}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Trend Charts */}
          {report.trend_data && typeof report.trend_data === 'object' && (report.trend_data as any).months?.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Revenue Trend</h3>
                <TrendChart data={(report.trend_data as any).revenue || []} labels={(report.trend_data as any).months || []} color="#22c55e" />
              </div>
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Proposals Won</h3>
                <TrendChart data={(report.trend_data as any).proposals_won || []} labels={(report.trend_data as any).months || []} color="#3b82f6" />
              </div>
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">New Contacts</h3>
                <TrendChart data={(report.trend_data as any).contacts || []} labels={(report.trend_data as any).months || []} color="#8b5cf6" />
              </div>
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Health Score</h3>
                <TrendChart data={(report.trend_data as any).health_scores || []} labels={(report.trend_data as any).months || []} color="#f59e0b" />
              </div>
            </div>
          )}

          {/* Win/Loss Section */}
          {deals && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5 mb-6">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                <Target className="h-4 w-4 text-amber-500" />
                Win/Loss Overview
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <MetricCard label="Total Deals" value={deals.total_deals} icon={FileSignature} color="text-blue-500" />
                <MetricCard label="Win Rate" value={`${deals.win_rate}%`} icon={TrendingUp} color="text-green-500" />
                <MetricCard label="Avg Deal Value" value={`$${(deals.avg_deal_value || 0).toLocaleString()}`} icon={DollarSign} color="text-amber-500" />
                <MetricCard label="Avg Cycle" value={`${deals.avg_cycle_days}d`} icon={Calendar} color="text-purple-500" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-600">{deals.wins}</p>
                  <p className="text-xs text-gray-500">Wins</p>
                </div>
                <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg text-center">
                  <p className="text-2xl font-bold text-red-600">{deals.losses}</p>
                  <p className="text-xs text-gray-500">Losses</p>
                </div>
                <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-center">
                  <p className="text-2xl font-bold text-yellow-600">{deals.pending}</p>
                  <p className="text-xs text-gray-500">Pending</p>
                </div>
              </div>

              {deals.total_revenue > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800 text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400">Total Revenue from Won Deals</p>
                  <p className="text-xl font-bold text-green-600">${deals.total_revenue.toLocaleString()}</p>
                </div>
              )}
            </div>
          )}

          {/* Meeting Patterns */}
          {report.meeting_patterns && typeof report.meeting_patterns === 'object' && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5 mb-6">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <Users className="h-4 w-4 text-amber-500" />
                Meeting Patterns
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Total Meetings</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{(report.meeting_patterns as any).total_meetings || 0}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Avg Duration</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{(report.meeting_patterns as any).avg_duration_minutes || 0}m</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Action Completion</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{(report.meeting_patterns as any).action_completion_rate || 0}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Insight</p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{(report.meeting_patterns as any).insight || '-'}</p>
                </div>
              </div>
            </div>
          )}

          {/* All Nudges */}
          {nudges.length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700 p-5">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                <Bell className="h-4 w-4 text-amber-500" />
                All Coaching Nudges ({nudges.length})
              </h2>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {nudges.map((n: any) => (
                  <NudgeCard key={n.id} nudge={n} onRead={(id) => markReadMut.mutate(id)} onActed={(id) => markActedMut.mutate(id)} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
