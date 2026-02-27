import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw, Play } from 'lucide-react';
import { listRules, toggleRule, processRules } from '@/api/recurring';
import { useAuthStore } from '@/stores/authStore';
import { formatDate } from '@/lib/utils';

const typeBadgeClasses: Record<string, string> = {
  expense: 'bg-red-100 text-red-700',
  income: 'bg-green-100 text-green-700',
  invoice: 'bg-blue-100 text-blue-700',
};

export default function RecurringPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';
  const isAdmin = user?.role === 'admin';

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ['recurring-rules', page],
    queryFn: () => listRules({ page, page_size: pageSize }),
  });

  const rules = data?.data ?? [];
  const totalPages = data?.meta?.total_pages ?? 1;

  const toggleMutation = useMutation({
    mutationFn: (id: string) => toggleRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
    },
  });

  const processMutation = useMutation({
    mutationFn: () => processRules(),
    onSuccess: (res) => {
      alert(`Successfully processed ${res.data.processed} rule(s).`);
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
    },
    onError: () => {
      alert('Failed to process rules.');
    },
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Recurring Transactions</h1>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <button
              onClick={() => processMutation.mutate()}
              disabled={processMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              {processMutation.isPending ? 'Processing...' : 'Process Rules'}
            </button>
          )}
          {canEdit && (
            <button
              onClick={() => navigate('/recurring/new')}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              New Rule
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" />
            Loading...
          </div>
        ) : rules.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <RefreshCw className="w-10 h-10 mb-3" />
            <p className="text-sm font-medium">No recurring rules found</p>
            <p className="text-xs mt-1">Create a rule to automate your transactions.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Frequency</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Next Run</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Last Run</th>
                    <th className="text-right px-4 py-3 font-medium text-gray-500">Run Count</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-500">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr
                      key={rule.id}
                      className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                      onClick={() => navigate(`/recurring/${rule.id}`)}
                    >
                      <td className="px-4 py-3 font-medium text-gray-900">{rule.name}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${typeBadgeClasses[rule.type] ?? 'bg-gray-100 text-gray-700'}`}
                        >
                          {rule.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 capitalize">{rule.frequency}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {rule.next_run_date ? formatDate(rule.next_run_date) : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {rule.last_run_date ? formatDate(rule.last_run_date) : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">{rule.run_count ?? 0}</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (canEdit) toggleMutation.mutate(rule.id);
                          }}
                          disabled={!canEdit || toggleMutation.isPending}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                            rule.is_active ? 'bg-blue-600' : 'bg-gray-300'
                          } ${!canEdit ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                              rule.is_active ? 'translate-x-4.5' : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
                <p className="text-sm text-gray-500">
                  Page {page} of {totalPages}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
