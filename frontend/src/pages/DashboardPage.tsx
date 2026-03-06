import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import {
  DollarSign,
  FileSignature,
  CalendarDays,
  Inbox,
  ChevronRight,
  ClipboardCheck,
  AlertCircle,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useAuthStore } from '@/stores/authStore'
import { listActivity } from '@/api/collaboration'
import { getUpcoming } from '@/api/calendar'
import { listPendingApprovals } from '@/api/accounting'
import { getInvoiceStats } from '@/api/invoices'
import { getProposalStats } from '@/api/proposals'
import { getUnreadCount } from '@/api/inbox'
import { schedulingApi } from '@/api/scheduling'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import { EVENT_TYPES } from '@/lib/constants'
import ActivityPanel from '@/components/dashboard/ActivityPanel'
import type { CalendarEvent, ActivityLogEntry, ExpenseApproval } from '@/types/models'

function buildChartData(activities: ActivityLogEntry[]) {
  const days: Record<string, number> = {}
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const key = d.toLocaleDateString('en-US', { weekday: 'short' })
    days[key] = 0
  }
  activities.forEach((a) => {
    const d = new Date(a.created_at)
    const key = d.toLocaleDateString('en-US', { weekday: 'short' })
    if (key in days) days[key]++
  })
  return Object.entries(days).map(([name, count]) => ({ name, count }))
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value)
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const firstName = user?.full_name?.split(' ')[0] ?? 'there'
  const todayStr = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  const { data: invoiceStatsData } = useQuery({
    queryKey: ['invoice-stats'],
    queryFn: getInvoiceStats,
  })

  const { data: proposalStatsData } = useQuery({
    queryKey: ['proposal-stats'],
    queryFn: getProposalStats,
  })

  const { data: unreadData } = useQuery({
    queryKey: ['inbox-unread'],
    queryFn: getUnreadCount,
    refetchInterval: 60000,
  })

  const { data: bookingsData } = useQuery({
    queryKey: ['upcoming-bookings'],
    queryFn: () => schedulingApi.listAllBookings(1, 5, 'confirmed'),
  })

  const { data: chartActivity } = useQuery({
    queryKey: ['activity', { page_size: 50 }],
    queryFn: () => listActivity({ page_size: 50 }),
  })

  const { data: upcomingData } = useQuery({
    queryKey: ['upcoming-deadlines'],
    queryFn: () => getUpcoming(7),
  })

  const { data: pendingApprovalsData } = useQuery({
    queryKey: ['pending-expense-approvals'],
    queryFn: () => listPendingApprovals(),
  })

  const invoiceStats = invoiceStatsData?.data
  const proposalStats = proposalStatsData?.data
  const unreadCount = unreadData?.data
  const bookings: any[] = (bookingsData as any)?.data ?? []
  const upcoming: CalendarEvent[] = upcomingData?.data ?? []
  const pendingApprovals: ExpenseApproval[] = pendingApprovalsData?.data ?? []
  const chartData = buildChartData(chartActivity?.data ?? [])

  const statCards = [
    {
      label: 'Total Revenue',
      value: formatCurrency(invoiceStats?.total_paid_this_month ?? 0),
      sublabel: 'Paid this month',
      icon: DollarSign,
      iconBg: 'bg-green-100 dark:bg-green-900/30',
      iconColor: 'text-green-600 dark:text-green-400',
      path: '/invoices',
    },
    {
      label: 'Outstanding',
      value: formatCurrency(invoiceStats?.total_outstanding ?? 0),
      sublabel: `${invoiceStats?.invoice_count ?? 0} invoices`,
      icon: AlertCircle,
      iconBg: 'bg-amber-100 dark:bg-amber-900/30',
      iconColor: 'text-amber-600 dark:text-amber-400',
      path: '/invoices',
    },
    {
      label: 'Proposals Pending',
      value: (proposalStats?.sent_count ?? 0) + (proposalStats?.viewed_count ?? 0),
      sublabel: `${proposalStats?.signed_count ?? 0} signed`,
      icon: FileSignature,
      iconBg: 'bg-blue-100 dark:bg-blue-900/30',
      iconColor: 'text-blue-600 dark:text-blue-400',
      path: '/proposals',
    },
    {
      label: 'Upcoming Meetings',
      value: bookings.length,
      sublabel: 'confirmed bookings',
      icon: CalendarDays,
      iconBg: 'bg-purple-100 dark:bg-purple-900/30',
      iconColor: 'text-purple-600 dark:text-purple-400',
      path: '/scheduling',
    },
    {
      label: 'Unread Messages',
      value: unreadCount?.total ?? 0,
      sublabel: `${unreadCount?.email ?? 0} email, ${unreadCount?.sms ?? 0} sms`,
      icon: Inbox,
      iconBg: 'bg-rose-100 dark:bg-rose-900/30',
      iconColor: 'text-rose-600 dark:text-rose-400',
      path: '/inbox',
    },
    {
      label: 'Pending Approvals',
      value: pendingApprovals.length,
      sublabel: 'expense approvals',
      icon: ClipboardCheck,
      iconBg: 'bg-orange-100 dark:bg-orange-900/30',
      iconColor: 'text-orange-600 dark:text-orange-400',
      path: '/expenses',
    },
  ]

  return (
    <div className="flex flex-1 min-h-0">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
        {/* Greeting */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Hello, {firstName}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              Here's your business at a glance
            </p>
          </div>
          <p className="text-sm text-gray-400 dark:text-gray-500 shrink-0">{todayStr}</p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {statCards.map((card) => {
            const Icon = card.icon
            return (
              <button
                key={card.label}
                onClick={() => navigate(card.path)}
                className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 flex items-center gap-4 hover:border-blue-200 dark:hover:border-blue-800 transition-colors text-left"
              >
                <div
                  className={`h-11 w-11 rounded-lg ${card.iconBg} ${card.iconColor} flex items-center justify-center shrink-0`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-gray-500 dark:text-gray-400">{card.label}</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{card.value}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">{card.sublabel}</p>
                </div>
              </button>
            )
          })}
        </div>

        {/* Chart */}
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
            Activity — Last 7 Days
          </h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 12, fill: '#9ca3af' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 12, fill: '#9ca3af' }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: '12px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#3b82f6' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Two-column: Upcoming Bookings + Upcoming Deadlines */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upcoming Bookings */}
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
            <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-purple-500" />
                Upcoming Bookings
              </h2>
              <button
                onClick={() => navigate('/scheduling')}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5"
              >
                View All <ChevronRight className="h-3 w-3" />
              </button>
            </div>
            <div className="divide-y divide-gray-50 dark:divide-gray-800">
              {bookings.length === 0 ? (
                <p className="p-5 text-sm text-gray-400 dark:text-gray-500 text-center">
                  No upcoming bookings
                </p>
              ) : (
                bookings.slice(0, 5).map((booking: any) => (
                  <div
                    key={booking.id}
                    className="px-5 py-3 flex items-center justify-between"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {booking.guest_name}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        {booking.guest_email}
                      </p>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0 ml-3">
                      {formatDate(booking.start_time)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Upcoming Deadlines */}
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
            <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Upcoming Deadlines
              </h2>
              <button
                onClick={() => navigate('/calendar')}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5"
              >
                View Calendar <ChevronRight className="h-3 w-3" />
              </button>
            </div>
            <div className="divide-y divide-gray-50 dark:divide-gray-800">
              {upcoming.length === 0 ? (
                <p className="p-5 text-sm text-gray-400 dark:text-gray-500 text-center">
                  No upcoming deadlines
                </p>
              ) : (
                upcoming.map((evt) => {
                  const typeInfo = EVENT_TYPES.find(
                    (t) => t.value === evt.event_type
                  )
                  return (
                    <div
                      key={evt.id}
                      className="px-5 py-3 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{
                            backgroundColor: typeInfo?.color ?? '#6b7280',
                          }}
                        />
                        <span
                          className={`text-sm truncate ${
                            evt.is_completed
                              ? 'line-through text-gray-400 dark:text-gray-500'
                              : 'text-gray-700 dark:text-gray-300'
                          }`}
                        >
                          {evt.title}
                        </span>
                      </div>
                      <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 ml-3">
                        {formatDate(evt.date)}
                      </span>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>

        {/* Pending Expense Approvals */}
        {pendingApprovals.length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 mt-6">
            <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-amber-500" />
                Pending Expense Approvals
                <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700">
                  {pendingApprovals.length}
                </span>
              </h2>
              <button
                onClick={() => navigate('/expenses')}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5"
              >
                View Expenses <ChevronRight className="h-3 w-3" />
              </button>
            </div>
            <div className="divide-y divide-gray-50 dark:divide-gray-800">
              {pendingApprovals.map((approval) => (
                <button
                  key={approval.id}
                  onClick={() => navigate(`/expenses/${approval.expense_id}`)}
                  className="w-full text-left px-5 py-3 flex items-center justify-between hover:bg-gray-50/50 dark:hover:bg-gray-800/50 transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">
                      Expense #{approval.expense_id.slice(0, 8)}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 ml-3">
                    {formatRelativeTime(approval.created_at)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Activity Panel (right side, xl+ only) */}
      <ActivityPanel />
    </div>
  )
}
