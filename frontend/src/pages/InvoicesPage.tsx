import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { Plus, Search, DollarSign, AlertTriangle, CheckCircle, FileText } from 'lucide-react';
import { listInvoices, getInvoiceStats } from '@/api/invoices';
import { useAuthStore } from '@/stores/authStore';
import { INVOICE_STATUSES } from '@/lib/constants';
import { formatDate } from '@/lib/utils';

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

export default function InvoicesPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);

  const statsQuery = useQuery({
    queryKey: ['invoice-stats'],
    queryFn: getInvoiceStats,
  });

  const invoicesQuery = useQuery({
    queryKey: ['invoices', { search, status: statusFilter, page }],
    queryFn: () =>
      listInvoices({
        search: search || undefined,
        status: statusFilter || undefined,
        page,
        page_size: 20,
      }),
  });

  const stats = statsQuery.data;
  const invoices = invoicesQuery.data?.data ?? [];
  const meta = invoicesQuery.data?.meta;

  const statCards = [
    {
      label: 'Total Outstanding',
      value: stats ? formatCurrency(stats.data.total_outstanding) : '—',
      icon: DollarSign,
      color: 'text-blue-600 bg-blue-50',
    },
    {
      label: 'Total Overdue',
      value: stats ? formatCurrency(stats.data.total_overdue) : '—',
      icon: AlertTriangle,
      color: 'text-red-600 bg-red-50',
    },
    {
      label: 'Paid This Month',
      value: stats ? formatCurrency(stats.data.total_paid_this_month) : '—',
      icon: CheckCircle,
      color: 'text-green-600 bg-green-50',
    },
    {
      label: 'Invoice Count',
      value: stats ? stats.data.invoice_count.toLocaleString() : '—',
      icon: FileText,
      color: 'text-purple-600 bg-purple-50',
    },
  ];

  const statusTabs = [{ value: '', label: 'All' }, ...INVOICE_STATUSES];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Invoices</h1>
        {canEdit && (
          <button
            onClick={() => navigate('/invoices/new')}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Invoice
          </button>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl shadow-sm border border-gray-100 p-5"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${card.color}`}>
                <card.icon className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm text-gray-500">{card.label}</p>
                <p className="text-xl font-semibold text-gray-900">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
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
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search invoices..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Invoice #</th>
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Client</th>
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Issue Date</th>
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Due Date</th>
              <th className="text-right px-5 py-3 text-gray-500 font-medium">Amount</th>
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {invoicesQuery.isLoading ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400">
                  Loading invoices...
                </td>
              </tr>
            ) : invoices.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-400">
                  No invoices found.
                </td>
              </tr>
            ) : (
              invoices.map((invoice) => {
                const statusInfo = INVOICE_STATUSES.find((s) => s.value === invoice.status);
                return (
                  <tr
                    key={invoice.id}
                    onClick={() => navigate(`/invoices/${invoice.id}`)}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3 font-medium text-gray-900">
                      {invoice.invoice_number}
                    </td>
                    <td className="px-5 py-3 text-gray-700">{invoice.contact?.company_name ?? '—'}</td>
                    <td className="px-5 py-3 text-gray-500">{formatDate(invoice.issue_date)}</td>
                    <td className="px-5 py-3 text-gray-500">{formatDate(invoice.due_date)}</td>
                    <td className="px-5 py-3 text-right font-medium text-gray-900">
                      {formatCurrency(invoice.total, invoice.currency)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusInfo?.color ?? 'bg-gray-100 text-gray-700'}`}
                      >
                        {statusInfo?.label ?? invoice.status}
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
          <p className="text-sm text-gray-500">
            Page {meta.page} of {meta.total_pages}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= meta.total_pages}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
