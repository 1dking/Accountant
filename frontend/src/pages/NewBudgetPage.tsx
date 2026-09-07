import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { ArrowLeft } from 'lucide-react';
import { createBudget } from '@/api/budgets';
import { listCategories } from '@/api/accounting';
import { PERIOD_TYPES } from '@/lib/constants';
import type { BudgetCreateData } from '@/api/budgets';
import { useTranslation } from 'react-i18next'

const currentYear = new Date().getFullYear();

export default function NewBudgetPage() {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [amount, setAmount] = useState('');
  const [periodType, setPeriodType] = useState('monthly');
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState<number | ''>('');
  const [categoryId, setCategoryId] = useState('');
  const [error, setError] = useState('');

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: () => listCategories(),
  });

  const categories = categoriesData?.data ?? [];

  const mutation = useMutation({
    mutationFn: (data: BudgetCreateData) => createBudget(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgetVsActual'] });
      queryClient.invalidateQueries({ queryKey: ['budgetAlerts'] });
      navigate('/budgets');
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to create budget. Please try again.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError(t('ui:NewBudgetPage.nameIsRequired'));
      return;
    }

    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError(t('ui:NewBudgetPage.amountMustBeAPositive'));
      return;
    }

    if (!year || year < 2000 || year > 2100) {
      setError(t('ui:NewBudgetPage.pleaseEnterAValidYear'));
      return;
    }

    const data: BudgetCreateData = {
      name: name.trim(),
      amount: parsedAmount,
      period_type: periodType,
      year,
    };

    if (categoryId) {
      data.category_id = categoryId;
    }

    if (periodType === 'monthly' && month !== '') {
      data.month = Number(month);
    }

    mutation.mutate(data);
  };

  return (
    <div className="p-6 max-w-2xl">
      {/* Back button */}
      <button
        onClick={() => navigate('/budgets')}
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
       {t('ui:NewBudgetPage.backToBudgets')}
      </button>

      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">{t('ui:NewBudgetPage.newBudget')}</h1>

      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewBudgetPage.name')} <span className="text-red-500">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('ui:NewBudgetPage.eGOfficeSuppliesBudget')}
              className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
              required
            />
          </div>

          {/* Amount */}
          <div>
            <label htmlFor="amount" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewBudgetPage.amount')} <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 text-sm">
                $
              </span>
              <input
                id="amount"
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 pl-7 pr-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                required
              />
            </div>
          </div>

          {/* Period Type */}
          <div>
            <label htmlFor="periodType" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewBudgetPage.periodType')}
            </label>
            <select
              id="periodType"
              value={periodType}
              onChange={(e) => {
                setPeriodType(e.target.value);
                if (e.target.value !== 'monthly') {
                  setMonth('');
                }
              }}
              className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
            >
              {PERIOD_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>
                  {pt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Year */}
          <div>
            <label htmlFor="year" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewBudgetPage.year')}
            </label>
            <input
              id="year"
              type="number"
              min="2000"
              max="2100"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>

          {/* Month (only for monthly period type) */}
          {periodType === 'monthly' && (
            <div>
              <label htmlFor="month" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
               {t('ui:NewBudgetPage.month')}
              </label>
              <select
                id="month"
                value={month}
                onChange={(e) => setMonth(e.target.value === '' ? '' : Number(e.target.value))}
                className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="">{t('ui:NewBudgetPage.selectAMonthOptional')}</option>
                <option value={1}>{t('ui:NewBudgetPage.january')}</option>
                <option value={2}>{t('ui:NewBudgetPage.february')}</option>
                <option value={3}>{t('ui:NewBudgetPage.march')}</option>
                <option value={4}>{t('ui:NewBudgetPage.april')}</option>
                <option value={5}>{t('ui:NewBudgetPage.may')}</option>
                <option value={6}>{t('ui:NewBudgetPage.june')}</option>
                <option value={7}>{t('ui:NewBudgetPage.july')}</option>
                <option value={8}>{t('ui:NewBudgetPage.august')}</option>
                <option value={9}>{t('ui:NewBudgetPage.september')}</option>
                <option value={10}>{t('ui:NewBudgetPage.october')}</option>
                <option value={11}>{t('ui:NewBudgetPage.november')}</option>
                <option value={12}>{t('ui:NewBudgetPage.december')}</option>
              </select>
            </div>
          )}

          {/* Category */}
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewBudgetPage.category')}
            </label>
            <select
              id="category"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="">{t('ui:NewBudgetPage.noCategoryOptional')}</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              {mutation.isPending ? t('ui:NewBudgetPage.creating') : t('ui:NewBudgetPage.createBudget')}
            </button>
            <button
              type="button"
              onClick={() => navigate('/budgets')}
              className="inline-flex items-center px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
            >
             {t('ui:NewBudgetPage.cancel')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
