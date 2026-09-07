import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { Plus, AlertTriangle, Trash2, Pencil, DollarSign } from 'lucide-react';
import { getBudgetVsActual, getBudgetAlerts, deleteBudget } from '@/api/budgets';
import { useAuthStore } from '@/stores/authStore';
import type { BudgetVsActual } from '@/types/models';
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import { uiLocale } from '@/lib/utils'

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat(uiLocale(), { style: 'currency', currency: 'USD' }).format(amount);

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);
const months = [
  { value: 0, label: i18n.t('ui:BudgetsPage.allMonths') },
  { value: 1, label: i18n.t('ui:BudgetsPage.january') },
  { value: 2, label: i18n.t('ui:BudgetsPage.february') },
  { value: 3, label: i18n.t('ui:BudgetsPage.march') },
  { value: 4, label: i18n.t('ui:BudgetsPage.april') },
  { value: 5, label: i18n.t('ui:BudgetsPage.may') },
  { value: 6, label: i18n.t('ui:BudgetsPage.june') },
  { value: 7, label: i18n.t('ui:BudgetsPage.july') },
  { value: 8, label: i18n.t('ui:BudgetsPage.august') },
  { value: 9, label: i18n.t('ui:BudgetsPage.september') },
  { value: 10, label: i18n.t('ui:BudgetsPage.october') },
  { value: 11, label: i18n.t('ui:BudgetsPage.november') },
  { value: 12, label: i18n.t('ui:BudgetsPage.december') },
];

function getProgressColor(percentage: number): string {
  if (percentage > 100) return 'bg-red-500';
  if (percentage >= 80) return 'bg-yellow-500';
  return 'bg-green-500';
}

function getAlertColor(percentage: number): string {
  if (percentage > 100) return 'text-red-600';
  return 'text-yellow-600';
}

export default function BudgetsPage() {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';

  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState(0);

  const { data: budgetVsActualData, isLoading } = useQuery({
    queryKey: ['budgetVsActual', year, month || undefined],
    queryFn: () => getBudgetVsActual(year, month || undefined),
  });

  const { data: alertsData } = useQuery({
    queryKey: ['budgetAlerts'],
    queryFn: () => getBudgetAlerts(),
  });

  const deleteM = useMutation({
    mutationFn: (id: string) => deleteBudget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgetVsActual'] });
      queryClient.invalidateQueries({ queryKey: ['budgetAlerts'] });
    },
  });

  const budgets: BudgetVsActual[] = budgetVsActualData?.data ?? [];
  const alerts: BudgetVsActual[] = (alertsData?.data ?? []).filter(
    (a) => (a.actual_amount / a.budgeted_amount) * 100 >= 80
  );

  const handleDelete = (id: string, name: string) => {
    if (window.confirm(t('ui:BudgetsPage.areYouSureYouWant', { name }))) {
      deleteM.mutate(id);
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('ui:BudgetsPage.budgets')}</h1>
        {canEdit && (
          <button
            onClick={() => navigate('/budgets/new')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
           {t('ui:BudgetsPage.newBudget')}
          </button>
        )}
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="mb-6 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:BudgetsPage.budgetAlerts')}</h2>
          </div>
          <div className="space-y-2">
            {alerts.map((alert) => {
              const percentage = (alert.actual_amount / alert.budgeted_amount) * 100;
              return (
                <div
                  key={alert.budget_id}
                  className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-950"
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={`w-4 h-4 ${getAlertColor(percentage)}`} />
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{alert.budget_name}</span>
                  </div>
                  <span className={`text-sm font-semibold ${getAlertColor(percentage)}`}>
                    {percentage.toFixed(0)}{t('ui:BudgetsPage.used')}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div>
          <label htmlFor="year" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
           {t('ui:BudgetsPage.year')}
          </label>
          <select
            id="year"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="block w-32 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="month" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
           {t('ui:BudgetsPage.month')}
          </label>
          <select
            id="month"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            className="block w-40 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            {months.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Budget vs Actual */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : budgets.length === 0 ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-12 text-center">
          <DollarSign className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">{t('ui:BudgetsPage.noBudgetsFound')}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {canEdit
              ? t('ui:BudgetsPage.getStartedByCreatingYour')
              : t('ui:BudgetsPage.noBudgetsHaveBeenSet')}
          </p>
          {canEdit && (
            <button
              onClick={() => navigate('/budgets/new')}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
             {t('ui:BudgetsPage.newBudget')}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {budgets.map((budget) => {
            const percentage = budget.budgeted_amount > 0 ? (budget.actual_amount / budget.budgeted_amount) * 100 : 0;
            const remaining = budget.budgeted_amount - budget.actual_amount;
            const clampedPercentage = Math.min(percentage, 100);

            return (
              <div
                key={budget.budget_id}
                className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{budget.budget_name}</h3>
                    {budget.category_name && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{budget.category_name}</p>
                    )}
                  </div>
                  {canEdit && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => navigate(`/budgets/${budget.budget_id}/edit`)}
                        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-blue-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title={t('ui:BudgetsPage.editBudget')}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(budget.budget_id, budget.budget_name)}
                        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        title={t('ui:BudgetsPage.deleteBudget')}
                        disabled={deleteM.isPending}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Progress bar */}
                <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 mb-3">
                  <div
                    className={`h-2 rounded-full transition-all ${getProgressColor(percentage)}`}
                    style={{ width: `${clampedPercentage}%` }}
                  />
                </div>

                {/* Amounts */}
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-4">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">{t('ui:BudgetsPage.budgeted')} </span>
                      <span className="font-medium text-gray-900 dark:text-gray-100">
                        {formatCurrency(budget.budgeted_amount)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">{t('ui:BudgetsPage.actual')} </span>
                      <span className="font-medium text-gray-900 dark:text-gray-100">
                        {formatCurrency(budget.actual_amount)}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">{t('ui:BudgetsPage.remaining')} </span>
                    <span
                      className={`font-medium ${remaining >= 0 ? 'text-green-600' : 'text-red-600'}`}
                    >
                      {formatCurrency(remaining)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
