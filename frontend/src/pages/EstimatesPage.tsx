import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { Plus, Search } from 'lucide-react';
import { listEstimates } from '@/api/estimates';
import { useAuthStore } from '@/stores/authStore';
import { ESTIMATE_STATUSES } from '@/lib/constants';
import { formatDate } from '@/lib/utils';

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

export default function EstimatesPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);

  const estimatesQuery = useQuery({
    queryKey: ['estimates', { search, status: statusFilter, page }],
    queryFn: () =>
      listEstimates({
        search: search || undefined,
        status: statusFilter || undefined,
        page,
        page_size: 20,
      }),
  });

  const estimates = estimatesQuery.data?.data ?? [];
  const meta = estimatesQuery.data?.meta;

  const statusTabs = [{ value: '', label: 'All' }, ...ESTIMATE_STATUSES];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Estimates</h1>
        {canEdit && (
          <button
            onClick={() => navigate('/estimates/new')}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Estimate
          </button>
        )}
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-1">
        {statusTabs.map((tab) => (
          <button
            key={tab.value}
            onClick={() => {
              setStatusFilter(tab.value);
              setPage(1);
            }}
            className={`px-3 py-1.5 text-sm rounded-lg whitespace-nowrap transition-colors ${
              statusFilter === tab.value
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
        <input
          type="text"
          placeholder="Search estimates..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-full pl-10 pr-4 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Estimate #</th>
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Client</th>
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Issue Date</th>
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Expiry Date</th>
              <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Amount</th>
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {estimatesQuery.isLoading ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400 dark:text-gray-500">
                  Loading estimates...
                </td>
              </tr>
            ) : estimates.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400 dark:text-gray-500">
                  No estimates found.
                </td>
              </tr>
            ) : (
              estimates.map((estimate) => {
                const statusInfo = ESTIMATE_STATUSES.find((s) => s.value === estimate.status);
                return (
                  <tr
                    key={estimate.id}
                    onClick={() => navigate(`/estimates/${estimate.id}`)}
                    className="border-b border-gray-50 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-gray-100">
                      {estimate.estimate_number}
                    </td>
                    <td className="px-5 py-3 text-gray-700 dark:text-gray-300">{estimate.contact?.company_name ?? '--'}</td>
                    <td className="px-5 py-3 text-gray-500 dark:text-gray-400">{formatDate(estimate.issue_date)}</td>
                    <td className="px-5 py-3 text-gray-500 dark:text-gray-400">{formatDate(estimate.expiry_date)}</td>
                    <td className="px-5 py-3 text-right font-medium text-gray-900 dark:text-gray-100">
                      {formatCurrency(estimate.total, estimate.currency)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusInfo?.color ?? 'bg-gray-100 dark:bg-gray-800 text-gray-700'}`}
                      >
                        {statusInfo?.label ?? estimate.status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Page {meta.page} of {meta.total_pages}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= meta.total_pages}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
