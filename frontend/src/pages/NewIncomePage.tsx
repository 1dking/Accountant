import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { createIncome } from '@/api/income';
import { listContacts } from '@/api/contacts';
import { INCOME_CATEGORIES, PAYMENT_METHODS } from '@/lib/constants';
import DocumentAttachment from '@/components/shared/DocumentAttachment';
import type { IncomeCreateData } from '@/api/income';
import type { DocumentListItem } from '@/types/models';

export default function NewIncomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<IncomeCreateData>({
    description: '',
    amount: 0,
    date: new Date().toISOString().split('T')[0],
    category: 'other',
    payment_method: '',
    contact_id: '',
    reference: '',
    notes: '',
  });

  const [error, setError] = useState('');
  const [selectedDocument, setSelectedDocument] = useState<DocumentListItem | null>(null);

  const { data: contactsData } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => listContacts(),
  });

  const contacts = contactsData?.data ?? [];

  const mutation = useMutation({
    mutationFn: (data: IncomeCreateData) => createIncome(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['income'] });
      queryClient.invalidateQueries({ queryKey: ['income-summary'] });
      navigate('/income');
    },
    onError: (err: any) => {
      setError(err?.response?.data?.message ?? err?.message ?? 'Failed to create income entry.');
    },
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === 'amount' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!form.description.trim()) {
      setError('Description is required.');
      return;
    }
    if (!form.amount || form.amount <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }
    if (!form.date) {
      setError('Date is required.');
      return;
    }

    const payload: IncomeCreateData = {
      description: form.description.trim(),
      amount: form.amount,
      date: form.date,
      category: form.category || 'other',
      ...(form.payment_method && { payment_method: form.payment_method }),
      ...(form.contact_id && { contact_id: form.contact_id }),
      ...(form.reference && { reference: form.reference.trim() }),
      ...(form.notes && { notes: form.notes.trim() }),
      ...(selectedDocument?.id && { document_id: selectedDocument.id }),
    };

    mutation.mutate(payload);
  };

  return (
    <div className="p-6 max-w-2xl">
      {/* Back Button */}
      <button
        onClick={() => navigate('/income')}
        className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Income
      </button>

      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">New Income</h1>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <input
              id="description"
              name="description"
              type="text"
              required
              value={form.description}
              onChange={handleChange}
              placeholder="Enter description"
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Amount & Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="amount" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Amount <span className="text-red-500">*</span>
              </label>
              <input
                id="amount"
                name="amount"
                type="number"
                required
                min="0.01"
                step="0.01"
                value={form.amount || ''}
                onChange={handleChange}
                placeholder="0.00"
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label htmlFor="date" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Date <span className="text-red-500">*</span>
              </label>
              <input
                id="date"
                name="date"
                type="date"
                required
                value={form.date}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Category & Payment Method */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="category" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Category
              </label>
              <select
                id="category"
                name="category"
                value={form.category}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900"
              >
                {INCOME_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="payment_method"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Payment Method
              </label>
              <select
                id="payment_method"
                name="payment_method"
                value={form.payment_method}
                onChange={handleChange}
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900"
              >
                <option value="">Select method</option>
                {PAYMENT_METHODS.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Contact */}
          <div>
            <label htmlFor="contact_id" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Contact
            </label>
            <select
              id="contact_id"
              name="contact_id"
              value={form.contact_id}
              onChange={handleChange}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900"
            >
              <option value="">None</option>
              {contacts.map((contact: any) => (
                <option key={contact.id} value={contact.id}>
                  {contact.name}
                </option>
              ))}
            </select>
          </div>

          {/* Reference */}
          <div>
            <label htmlFor="reference" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Reference
            </label>
            <input
              id="reference"
              name="reference"
              type="text"
              value={form.reference}
              onChange={handleChange}
              placeholder="e.g. Invoice #1234"
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <DocumentAttachment
            selectedDocument={selectedDocument}
            onDocumentSelect={setSelectedDocument}
            onMetadataExtracted={(meta) => {
              setForm((prev) => ({
                ...prev,
                ...(meta.total_amount && { amount: Number(meta.total_amount) }),
                ...(meta.date && { date: String(meta.date) }),
                ...(meta.vendor_name && { description: `Income from ${meta.vendor_name}` }),
                ...(meta.payment_method && { payment_method: String(meta.payment_method) }),
                ...(meta.receipt_number && { reference: String(meta.receipt_number) }),
              }))
            }}
            label="Receipt / Invoice"
          />

          {/* Notes */}
          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Notes
            </label>
            <textarea
              id="notes"
              name="notes"
              rows={3}
              value={form.notes}
              onChange={handleChange}
              placeholder="Additional notes..."
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Income
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
