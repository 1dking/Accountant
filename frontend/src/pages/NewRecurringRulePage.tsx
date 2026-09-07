import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { createRule } from '@/api/recurring';
import { RECURRING_TYPES, FREQUENCIES } from '@/lib/constants';
import { useTranslation } from 'react-i18next'

const defaultTemplateData: Record<string, string> = {
  expense: JSON.stringify({ vendor_name: '', description: '', amount: 0, category: '' }, null, 2),
  income: JSON.stringify({ description: '', amount: 0, category: '' }, null, 2),
  invoice: JSON.stringify({ contact_id: '', notes: '' }, null, 2),
};

export default function NewRecurringRulePage() {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [type, setType] = useState('expense');
  const [frequency, setFrequency] = useState('monthly');
  const [nextRunDate, setNextRunDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [templateJson, setTemplateJson] = useState(defaultTemplateData['expense']);
  const [jsonError, setJsonError] = useState('');

  const handleTypeChange = (newType: string) => {
    setType(newType);
    setTemplateJson(defaultTemplateData[newType] ?? '{}');
    setJsonError('');
  };

  const mutation = useMutation({
    mutationFn: (data: Parameters<typeof createRule>[0]) => createRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
      navigate('/recurring');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    let parsedTemplate: Record<string, unknown>;
    try {
      parsedTemplate = JSON.parse(templateJson);
      setJsonError('');
    } catch {
      setJsonError('Invalid JSON. Please check the format.');
      return;
    }

    mutation.mutate({
      name,
      type,
      frequency,
      next_run_date: nextRunDate,
      end_date: endDate || undefined,
      template_data: parsedTemplate,
    });
  };

  return (
    <div className="p-6 max-w-2xl">
      <button
        onClick={() => navigate('/recurring')}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
       {t('ui:NewRecurringRulePage.backToRecurringTransactions')}
      </button>

      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-6">{t('ui:NewRecurringRulePage.newRecurringRule')}</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.name')} <span className="text-red-500">*</span>
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('ui:NewRecurringRulePage.eGMonthlyRent')}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Type */}
          <div>
            <label htmlFor="type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.type')}
            </label>
            <select
              id="type"
              value={type}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900"
            >
              {RECURRING_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Frequency */}
          <div>
            <label htmlFor="frequency" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.frequency')}
            </label>
            <select
              id="frequency"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900"
            >
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          {/* Next Run Date */}
          <div>
            <label htmlFor="next_run_date" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.nextRunDate')} <span className="text-red-500">*</span>
            </label>
            <input
              id="next_run_date"
              type="date"
              required
              value={nextRunDate}
              onChange={(e) => setNextRunDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* End Date */}
          <div>
            <label htmlFor="end_date" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.endDate')} <span className="text-gray-400 dark:text-gray-500">{t('ui:NewRecurringRulePage.optional')}</span>
            </label>
            <input
              id="end_date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Template Data */}
          <div>
            <label htmlFor="template_data" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
             {t('ui:NewRecurringRulePage.templateDataJson')}
            </label>
            <textarea
              id="template_data"
              rows={6}
              value={templateJson}
              onChange={(e) => {
                setTemplateJson(e.target.value);
                setJsonError('');
              }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {jsonError && <p className="mt-1 text-xs text-red-600">{jsonError}</p>}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? t('ui:NewRecurringRulePage.creating') : t('ui:NewRecurringRulePage.createRule')}
          </button>
          <button
            type="button"
            onClick={() => navigate('/recurring')}
            className="px-5 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          >
           {t('ui:NewRecurringRulePage.cancel')}
          </button>
        </div>

        {mutation.isError && (
          <p className="text-sm text-red-600">{t('ui:NewRecurringRulePage.failedToCreateRulePlease')}</p>
        )}
      </form>
    </div>
  );
}
