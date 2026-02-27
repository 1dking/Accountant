import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
} from 'recharts'
import {
  Download,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Calculator,
  Receipt,
  Wallet,
  AlertTriangle,
  BarChart3,
} from 'lucide-react'
import {
  getProfitLoss,
  getTaxSummary,
  getCashFlow,
  getAccountsSummary,
  getARaging,
  getAPaging,
  getProfitLossPdfUrl,
  getTaxSummaryPdfUrl,
} from '@/api/reports'
import type {
  ProfitLossReport,
  TaxSummary,
  CashFlowReport,
  AccountsSummary,
  AgingReport,
  AgingBucket,
  CategoryAmount,
} from '@/types/models'

const formatCurrency = (amount: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)

const tabs = ['Profit & Loss', 'Tax Summary', 'Cash Flow', 'Accounts', 'AR Aging', 'AP Aging'] as const
type Tab = (typeof tabs)[number]

const currentYear = new Date().getFullYear()
const yearStart = `${currentYear}-01-01`
const today = new Date().toISOString().split('T')[0]

// ─── Profit & Loss Tab ───────────────────────────────────────────────────────

function ProfitLossTab() {
  const [dateFrom, setDateFrom] = useState(yearStart)
  const [dateTo, setDateTo] = useState(today)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['profitLoss', dateFrom, dateTo],
    queryFn: () => getProfitLoss(dateFrom, dateTo),
    enabled: !!dateFrom && !!dateTo,
  })

  const report: ProfitLossReport | undefined = data?.data

  const chartData = report
    ? [
        ...report.income_by_category.map((c) => ({
          category: c.category,
          Income: c.amount,
          Expenses: 0,
        })),
        ...report.expenses_by_category.map((c) => ({
          category: c.category,
          Income: 0,
          Expenses: c.amount,
        })),
      ]
    : []

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {report && (
            <a
              href={getProfitLossPdfUrl(dateFrom, dateTo)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              <Download className="w-4 h-4" />
              Download PDF
            </a>
          )}
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load Profit & Loss report." />}

      {report && (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="Total Income"
              value={formatCurrency(report.total_income)}
              icon={<TrendingUp className="w-5 h-5" />}
              color="green"
            />
            <StatCard
              label="Total Expenses"
              value={formatCurrency(report.total_expenses)}
              icon={<TrendingDown className="w-5 h-5" />}
              color="red"
            />
            <StatCard
              label="Net Profit"
              value={formatCurrency(report.net_profit)}
              icon={<DollarSign className="w-5 h-5" />}
              color={report.net_profit >= 0 ? 'blue' : 'red'}
            />
          </div>

          {/* Bar Chart */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Income vs Expenses by Category</h3>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" tickFormatter={(v: number) => formatCurrency(v)} />
                  <YAxis type="category" dataKey="category" width={140} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value) => formatCurrency(Number(value ?? 0))} />
                  <Legend />
                  <Bar dataKey="Income" fill="#22c55e" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="Expenses" fill="#ef4444" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Breakdown Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CategoryTable title="Income Breakdown" items={report.income_by_category} color="green" />
            <CategoryTable title="Expenses Breakdown" items={report.expenses_by_category} color="red" />
          </div>
        </>
      )}
    </div>
  )
}

function CategoryTable({
  title,
  items,
  color,
}: {
  title: string
  items: CategoryAmount[]
  color: 'green' | 'red'
}) {
  const total = items.reduce((sum, i) => sum + i.amount, 0)
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
      </div>
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50 text-left text-sm text-gray-500">
            <th className="px-5 py-3 font-medium">Category</th>
            <th className="px-5 py-3 font-medium text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.category} className="border-t border-gray-50 hover:bg-gray-50 transition-colors">
              <td className="px-5 py-3 text-sm text-gray-700">{item.category}</td>
              <td
                className={`px-5 py-3 text-sm text-right font-medium ${
                  color === 'green' ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {formatCurrency(item.amount)}
              </td>
            </tr>
          ))}
          <tr className="border-t-2 border-gray-200 bg-gray-50 font-semibold">
            <td className="px-5 py-3 text-sm text-gray-800">Total</td>
            <td
              className={`px-5 py-3 text-sm text-right ${
                color === 'green' ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(total)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

// ─── Tax Summary Tab ─────────────────────────────────────────────────────────

function TaxSummaryTab() {
  const [year, setYear] = useState(currentYear)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['taxSummary', year],
    queryFn: () => getTaxSummary(year),
  })

  const summary: TaxSummary | undefined = data?.data

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2000}
              max={2099}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-28"
            />
          </div>
          {summary && (
            <a
              href={getTaxSummaryPdfUrl(year)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              <Download className="w-4 h-4" />
              Download PDF
            </a>
          )}
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load Tax Summary." />}

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <BorderTopCard
            label="Taxable Income"
            value={formatCurrency(summary.taxable_income)}
            icon={<DollarSign className="w-5 h-5" />}
            borderColor="border-blue-500"
            iconBg="bg-blue-50 text-blue-600"
          />
          <BorderTopCard
            label="Deductible Expenses"
            value={formatCurrency(summary.deductible_expenses)}
            icon={<Receipt className="w-5 h-5" />}
            borderColor="border-amber-500"
            iconBg="bg-amber-50 text-amber-600"
          />
          <BorderTopCard
            label="Tax Collected"
            value={formatCurrency(summary.tax_collected)}
            icon={<Calculator className="w-5 h-5" />}
            borderColor="border-green-500"
            iconBg="bg-green-50 text-green-600"
          />
          <BorderTopCard
            label="Net Taxable"
            value={formatCurrency(summary.net_taxable)}
            icon={<Wallet className="w-5 h-5" />}
            borderColor="border-purple-500"
            iconBg="bg-purple-50 text-purple-600"
          />
        </div>
      )}
    </div>
  )
}

function BorderTopCard({
  label,
  value,
  icon,
  borderColor,
  iconBg,
}: {
  label: string
  value: string
  icon: React.ReactNode
  borderColor: string
  iconBg: string
}) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 border-t-4 ${borderColor} p-5`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <div className={`p-2 rounded-lg ${iconBg}`}>{icon}</div>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

// ─── Cash Flow Tab ───────────────────────────────────────────────────────────

function CashFlowTab() {
  const [dateFrom, setDateFrom] = useState(yearStart)
  const [dateTo, setDateTo] = useState(today)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cashFlow', dateFrom, dateTo],
    queryFn: () => getCashFlow(dateFrom, dateTo),
    enabled: !!dateFrom && !!dateTo,
  })

  const report: CashFlowReport | undefined = data?.data

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load Cash Flow report." />}

      {report && report.periods.length > 0 && (
        <>
          {/* Line Chart */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Cash Flow Over Time</h3>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={report.periods} margin={{ left: 20, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period_label" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v: number) => formatCurrency(v)} />
                <Tooltip formatter={(value) => formatCurrency(Number(value ?? 0))} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="income"
                  name="Income"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="expenses"
                  name="Expenses"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="net"
                  name="Net"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Cash Flow Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-800">Period Details</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 text-left text-sm text-gray-500">
                    <th className="px-5 py-3 font-medium">Period</th>
                    <th className="px-5 py-3 font-medium text-right">Income</th>
                    <th className="px-5 py-3 font-medium text-right">Expenses</th>
                    <th className="px-5 py-3 font-medium text-right">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {report.periods.map((period) => (
                    <tr
                      key={period.period_label}
                      className="border-t border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-5 py-3 text-sm text-gray-700 font-medium">{period.period_label}</td>
                      <td className="px-5 py-3 text-sm text-right text-green-600 font-medium">
                        {formatCurrency(period.income)}
                      </td>
                      <td className="px-5 py-3 text-sm text-right text-red-600 font-medium">
                        {formatCurrency(period.expenses)}
                      </td>
                      <td
                        className={`px-5 py-3 text-sm text-right font-medium ${
                          period.net >= 0 ? 'text-blue-600' : 'text-red-600'
                        }`}
                      >
                        {formatCurrency(period.net)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ─── Accounts Tab ────────────────────────────────────────────────────────────

function AccountsTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['accountsSummary'],
    queryFn: () => getAccountsSummary(),
  })

  const summary: AccountsSummary | undefined = data?.data

  return (
    <div className="space-y-6">
      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load Accounts Summary." />}

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Receivable"
            value={formatCurrency(summary.total_receivable)}
            icon={<TrendingUp className="w-5 h-5" />}
            color="green"
          />
          <StatCard
            label="Total Payable"
            value={formatCurrency(summary.total_payable)}
            icon={<TrendingDown className="w-5 h-5" />}
            color="amber"
          />
          <StatCard
            label="Overdue Receivable"
            value={formatCurrency(summary.overdue_receivable)}
            icon={<AlertTriangle className="w-5 h-5" />}
            color={summary.overdue_receivable > 0 ? 'red' : 'green'}
          />
          <StatCard
            label="Net Position"
            value={formatCurrency(summary.net_position)}
            icon={<Wallet className="w-5 h-5" />}
            color={summary.net_position >= 0 ? 'blue' : 'red'}
          />
        </div>
      )}
    </div>
  )
}

// ─── AR Aging Tab ───────────────────────────────────────────────────────────

function ARAgingTab() {
  const [asOfDate, setAsOfDate] = useState(today)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['arAging', asOfDate],
    queryFn: () => getARaging(asOfDate),
    enabled: !!asOfDate,
  })

  const report: AgingReport | undefined = data?.data

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">As of Date</label>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load AR Aging report." />}

      {report && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard
              label="Current"
              value={formatCurrency(report.grand_totals.current)}
              icon={<DollarSign className="w-5 h-5" />}
              color="green"
            />
            <StatCard
              label="1-30 Days"
              value={formatCurrency(report.grand_totals.days_1_30)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="amber"
            />
            <StatCard
              label="31-60 Days"
              value={formatCurrency(report.grand_totals.days_31_60)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="amber"
            />
            <StatCard
              label="61-90 Days"
              value={formatCurrency(report.grand_totals.days_61_90)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="red"
            />
            <StatCard
              label="90+ Days"
              value={formatCurrency(report.grand_totals.days_90_plus)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="red"
            />
            <StatCard
              label="Total Outstanding"
              value={formatCurrency(report.grand_totals.total)}
              icon={<Wallet className="w-5 h-5" />}
              color="blue"
            />
          </div>

          {/* Aging Table */}
          <AgingTable
            title="Accounts Receivable Aging"
            buckets={report.buckets}
            grandTotals={report.grand_totals}
            nameLabel="Customer"
          />
        </>
      )}
    </div>
  )
}

// ─── AP Aging Tab ───────────────────────────────────────────────────────────

function APAgingTab() {
  const [asOfDate, setAsOfDate] = useState(today)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['apAging', asOfDate],
    queryFn: () => getAPaging(asOfDate),
    enabled: !!asOfDate,
  })

  const report: AgingReport | undefined = data?.data

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">As of Date</label>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Failed to load AP Aging report." />}

      {report && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard
              label="Current"
              value={formatCurrency(report.grand_totals.current)}
              icon={<DollarSign className="w-5 h-5" />}
              color="green"
            />
            <StatCard
              label="1-30 Days"
              value={formatCurrency(report.grand_totals.days_1_30)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="amber"
            />
            <StatCard
              label="31-60 Days"
              value={formatCurrency(report.grand_totals.days_31_60)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="amber"
            />
            <StatCard
              label="61-90 Days"
              value={formatCurrency(report.grand_totals.days_61_90)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="red"
            />
            <StatCard
              label="90+ Days"
              value={formatCurrency(report.grand_totals.days_90_plus)}
              icon={<AlertTriangle className="w-5 h-5" />}
              color="red"
            />
            <StatCard
              label="Total Outstanding"
              value={formatCurrency(report.grand_totals.total)}
              icon={<Wallet className="w-5 h-5" />}
              color="blue"
            />
          </div>

          {/* Aging Table */}
          <AgingTable
            title="Accounts Payable Aging"
            buckets={report.buckets}
            grandTotals={report.grand_totals}
            nameLabel="Vendor"
          />
        </>
      )}
    </div>
  )
}

// ─── Aging Table Component ──────────────────────────────────────────────────

function AgingTable({
  title,
  buckets,
  grandTotals,
  nameLabel,
}: {
  title: string
  buckets: AgingBucket[]
  grandTotals: AgingBucket | { current: number; days_1_30: number; days_31_60: number; days_61_90: number; days_90_plus: number; total: number }
  nameLabel: string
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left text-sm text-gray-500">
              <th className="px-5 py-3 font-medium">{nameLabel}</th>
              <th className="px-5 py-3 font-medium text-right">Current</th>
              <th className="px-5 py-3 font-medium text-right">1-30 Days</th>
              <th className="px-5 py-3 font-medium text-right">31-60 Days</th>
              <th className="px-5 py-3 font-medium text-right">61-90 Days</th>
              <th className="px-5 py-3 font-medium text-right">90+ Days</th>
              <th className="px-5 py-3 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {buckets.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-sm text-gray-400">
                  No outstanding items found.
                </td>
              </tr>
            )}
            {buckets.map((bucket) => (
              <tr
                key={bucket.name}
                className="border-t border-gray-50 hover:bg-gray-50 transition-colors"
              >
                <td className="px-5 py-3 text-sm text-gray-700 font-medium">{bucket.name}</td>
                <td className="px-5 py-3 text-sm text-right text-green-600">
                  {bucket.current > 0 ? formatCurrency(bucket.current) : '-'}
                </td>
                <td className="px-5 py-3 text-sm text-right text-amber-600">
                  {bucket.days_1_30 > 0 ? formatCurrency(bucket.days_1_30) : '-'}
                </td>
                <td className="px-5 py-3 text-sm text-right text-amber-600">
                  {bucket.days_31_60 > 0 ? formatCurrency(bucket.days_31_60) : '-'}
                </td>
                <td className="px-5 py-3 text-sm text-right text-red-600">
                  {bucket.days_61_90 > 0 ? formatCurrency(bucket.days_61_90) : '-'}
                </td>
                <td className="px-5 py-3 text-sm text-right text-red-700 font-medium">
                  {bucket.days_90_plus > 0 ? formatCurrency(bucket.days_90_plus) : '-'}
                </td>
                <td className="px-5 py-3 text-sm text-right text-gray-900 font-semibold">
                  {formatCurrency(bucket.total)}
                </td>
              </tr>
            ))}
            {buckets.length > 0 && (
              <tr className="border-t-2 border-gray-200 bg-gray-50 font-semibold">
                <td className="px-5 py-3 text-sm text-gray-800">Grand Total</td>
                <td className="px-5 py-3 text-sm text-right text-green-700">
                  {formatCurrency(grandTotals.current)}
                </td>
                <td className="px-5 py-3 text-sm text-right text-amber-700">
                  {formatCurrency(grandTotals.days_1_30)}
                </td>
                <td className="px-5 py-3 text-sm text-right text-amber-700">
                  {formatCurrency(grandTotals.days_31_60)}
                </td>
                <td className="px-5 py-3 text-sm text-right text-red-700">
                  {formatCurrency(grandTotals.days_61_90)}
                </td>
                <td className="px-5 py-3 text-sm text-right text-red-800">
                  {formatCurrency(grandTotals.days_90_plus)}
                </td>
                <td className="px-5 py-3 text-sm text-right text-gray-900">
                  {formatCurrency(grandTotals.total)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Shared Components ───────────────────────────────────────────────────────

const colorMap = {
  green: { bg: 'bg-green-50', text: 'text-green-600', valueTxt: 'text-green-700' },
  red: { bg: 'bg-red-50', text: 'text-red-600', valueTxt: 'text-red-700' },
  blue: { bg: 'bg-blue-50', text: 'text-blue-600', valueTxt: 'text-blue-700' },
  amber: { bg: 'bg-amber-50', text: 'text-amber-600', valueTxt: 'text-amber-700' },
} as const

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string
  value: string
  icon: React.ReactNode
  color: keyof typeof colorMap
}) {
  const c = colorMap[color]
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <div className={`p-2 rounded-lg ${c.bg} ${c.text}`}>{icon}</div>
      </div>
      <p className={`text-2xl font-bold ${c.valueTxt}`}>{value}</p>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-10 flex items-center justify-center">
      <div className="flex items-center gap-3 text-gray-400">
        <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        <span className="text-sm">Loading report...</span>
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="bg-red-50 rounded-xl border border-red-200 p-5 flex items-center gap-3 text-red-700">
      <AlertTriangle className="w-5 h-5 flex-shrink-0" />
      <span className="text-sm">{message}</span>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Profit & Loss')

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <BarChart3 className="w-7 h-7 text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900">Financial Reports</h1>
        </div>
        <p className="text-sm text-gray-500">Generate and review financial reports for your business.</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium transition-colors whitespace-nowrap ${
                activeTab === tab
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'Profit & Loss' && <ProfitLossTab />}
      {activeTab === 'Tax Summary' && <TaxSummaryTab />}
      {activeTab === 'Cash Flow' && <CashFlowTab />}
      {activeTab === 'Accounts' && <AccountsTab />}
      {activeTab === 'AR Aging' && <ARAgingTab />}
      {activeTab === 'AP Aging' && <APAgingTab />}
    </div>
  )
}
