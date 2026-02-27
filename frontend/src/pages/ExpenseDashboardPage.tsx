import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getExpenseSummary } from '@/api/accounting'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts'
import { ArrowLeft, Download, DollarSign, TrendingUp, Hash, Tag } from 'lucide-react'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(amount)
}

export default function ExpenseDashboardPage() {
  const navigate = useNavigate()
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)

  const { data, isLoading } = useQuery({
    queryKey: ['expense-summary', year],
    queryFn: () => getExpenseSummary({ year }),
  })

  const summary = data?.data
  const topCategory = summary?.by_category?.[0]

  const monthlyData = (summary?.by_month ?? []).map((m) => ({
    name: MONTH_NAMES[m.month - 1],
    total: m.total,
    count: m.count,
  }))

  const categoryData = (summary?.by_category ?? []).map((c) => ({
    name: c.category_name,
    value: c.total,
    color: c.category_color || '#6b7280',
    count: c.count,
  }))

  const vendorData = (summary?.top_vendors ?? []).slice(0, 8).map((v) => ({
    name: v.vendor_name.length > 15 ? v.vendor_name.slice(0, 15) + '...' : v.vendor_name,
    total: v.total,
    count: v.count,
  }))

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/expenses')}
            className="flex items-center gap-1 text-sm text-blue-600 hover:underline mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to expenses
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Expense Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value))}
            className="px-3 py-2 text-sm border rounded-lg bg-white"
          >
            {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <a
            href={`/api/accounting/export/csv`}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </a>
          <a
            href={`/api/accounting/export/xlsx`}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium border rounded-lg hover:bg-gray-50"
          >
            <Download className="h-4 w-4" />
            Export XLSX
          </a>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse h-24 bg-gray-200 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={<DollarSign className="h-5 w-5 text-blue-600" />}
              label="Total Spend"
              value={formatCurrency(summary?.total_amount ?? 0)}
              bg="bg-blue-50"
            />
            <StatCard
              icon={<Hash className="h-5 w-5 text-green-600" />}
              label="Expenses"
              value={String(summary?.expense_count ?? 0)}
              bg="bg-green-50"
            />
            <StatCard
              icon={<TrendingUp className="h-5 w-5 text-purple-600" />}
              label="Average"
              value={formatCurrency(summary?.average_amount ?? 0)}
              bg="bg-purple-50"
            />
            <StatCard
              icon={<Tag className="h-5 w-5 text-orange-600" />}
              label="Top Category"
              value={topCategory?.category_name ?? 'N/A'}
              bg="bg-orange-50"
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Monthly trend */}
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Monthly Spending</h3>
              {monthlyData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={monthlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
                    <Tooltip
                      formatter={(value) => [formatCurrency(Number(value ?? 0)), 'Spend']}
                    />
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={{ fill: '#3b82f6' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-gray-400">
                  No data for {year}
                </div>
              )}
            </div>

            {/* Category breakdown */}
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-semibold text-gray-900 mb-4">By Category</h3>
              {categoryData.length > 0 ? (
                <div className="flex gap-4">
                  <ResponsiveContainer width="50%" height={250}>
                    <PieChart>
                      <Pie
                        data={categoryData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={90}
                        dataKey="value"
                        paddingAngle={2}
                      >
                        {categoryData.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) => formatCurrency(Number(value ?? 0))}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex-1 space-y-1.5 overflow-y-auto max-h-[250px]">
                    {categoryData.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <div
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: c.color }}
                        />
                        <span className="text-gray-700 truncate flex-1">{c.name}</span>
                        <span className="text-gray-900 font-medium">{formatCurrency(c.value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-gray-400">
                  No expenses yet
                </div>
              )}
            </div>
          </div>

          {/* Top vendors */}
          <div className="bg-white rounded-lg border p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Top Vendors</h3>
            {vendorData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={vendorData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value) => [formatCurrency(Number(value ?? 0)), 'Spend']} />
                  <Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-gray-400">
                No vendor data
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, bg }: { icon: React.ReactNode; label: string; value: string; bg: string }) {
  return (
    <div className={`${bg} rounded-lg p-4`}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs font-medium text-gray-500 uppercase">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900">{value}</p>
    </div>
  )
}
