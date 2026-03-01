import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { ArrowLeft, Plus, Trash2 } from 'lucide-react';
import { createInvoice } from '@/api/invoices';
import { listContacts } from '@/api/contacts';
import { getCompanySettings } from '@/api/settings';
import type { InvoiceLineItemData, InvoiceCreateData } from '@/api/invoices';

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

const emptyLineItem = (): InvoiceLineItemData => ({
  description: '',
  quantity: 1,
  unit_price: 0,
  tax_rate: 0,
});

export default function NewInvoicePage() {
  const navigate = useNavigate();

  const [contactId, setContactId] = useState('');
  const [issueDate, setIssueDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [dueDate, setDueDate] = useState('');
  const [taxRate, setTaxRate] = useState<number>(0);
  const [discountAmount, setDiscountAmount] = useState<number>(0);
  const [currency, setCurrency] = useState('USD');
  const [notes, setNotes] = useState('');
  const [paymentTerms, setPaymentTerms] = useState('');
  const [lineItems, setLineItems] = useState<InvoiceLineItemData[]>([
    emptyLineItem(),
  ]);

  const contactsQuery = useQuery({
    queryKey: ['contacts', 'client-list'],
    queryFn: () => listContacts({ type: 'client', page_size: 100 }),
  });

  const settingsQuery = useQuery({
    queryKey: ['company-settings'],
    queryFn: getCompanySettings,
  });

  // Auto-fill defaults from company settings
  useEffect(() => {
    const settings = settingsQuery.data?.data;
    if (!settings) return;
    if (settings.default_tax_rate?.rate && taxRate === 0) {
      setTaxRate(settings.default_tax_rate.rate);
    }
    if (settings.default_currency) {
      setCurrency(settings.default_currency);
    }
  }, [settingsQuery.data]);

  const contacts = contactsQuery.data?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (data: InvoiceCreateData) => createInvoice(data),
    onSuccess: (response) => {
      navigate(`/invoices/${response.data.id}`);
    },
  });

  // Calculations
  const totals = useMemo(() => {
    const subtotal = lineItems.reduce(
      (sum, item) => sum + item.quantity * item.unit_price,
      0
    );

    const itemTax = lineItems.reduce((sum, item) => {
      const rate = item.tax_rate ?? taxRate;
      return sum + item.quantity * item.unit_price * (rate / 100);
    }, 0);

    const total = subtotal + itemTax - discountAmount;

    return { subtotal, tax: itemTax, discount: discountAmount, total };
  }, [lineItems, taxRate, discountAmount]);

  const updateLineItem = (
    index: number,
    field: keyof InvoiceLineItemData,
    value: string | number
  ) => {
    setLineItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const addLineItem = () => {
    setLineItems((prev) => [...prev, emptyLineItem()]);
  };

  const removeLineItem = (index: number) => {
    if (lineItems.length <= 1) return;
    setLineItems((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const validLineItems = lineItems.filter(
      (item) => item.description.trim() && item.quantity > 0 && item.unit_price > 0
    );

    if (validLineItems.length === 0) return;

    const data: InvoiceCreateData = {
      contact_id: contactId,
      issue_date: issueDate,
      due_date: dueDate,
      line_items: validLineItems.map((item) => ({
        ...item,
        tax_rate: item.tax_rate || taxRate || undefined,
      })),
      ...(taxRate > 0 && { tax_rate: taxRate }),
      ...(discountAmount > 0 && { discount_amount: discountAmount }),
      ...(currency !== 'USD' && { currency }),
      ...(notes.trim() && { notes: notes.trim() }),
      ...(paymentTerms.trim() && { payment_terms: paymentTerms.trim() }),
    };

    createMutation.mutate(data);
  };

  return (
    <div className="p-6 max-w-2xl">
      {/* Back Button */}
      <button
        onClick={() => navigate('/invoices')}
        className="flex items-center gap-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span className="text-sm">Back to Invoices</span>
      </button>

      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-6">New Invoice</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Contact & Dates */}
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Client <span className="text-red-500">*</span>
            </label>
            <select
              required
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Select a client...</option>
              {contacts.map((contact) => (
                <option key={contact.id} value={contact.id}>
                  {contact.company_name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Issue Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                required
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Due Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                required
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="CAD">CAD</option>
                <option value="AUD">AUD</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Global Tax Rate (%)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={taxRate || ''}
                onChange={(e) => setTaxRate(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="0"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Discount Amount
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={discountAmount || ''}
                onChange={(e) => setDiscountAmount(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="0.00"
              />
            </div>
          </div>
        </div>

        {/* Line Items */}
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Line Items</h2>
            <button
              type="button"
              onClick={addLineItem}
              className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Item
            </button>
          </div>

          <div className="space-y-3">
            {/* Header */}
            <div className="hidden sm:grid sm:grid-cols-12 gap-2 text-xs text-gray-500 dark:text-gray-400 font-medium px-1">
              <div className="col-span-5">Description</div>
              <div className="col-span-2">Qty</div>
              <div className="col-span-2">Unit Price</div>
              <div className="col-span-2">Tax %</div>
              <div className="col-span-1"></div>
            </div>

            {lineItems.map((item, index) => (
              <div
                key={index}
                className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-start"
              >
                <div className="sm:col-span-5">
                  <input
                    type="text"
                    required
                    value={item.description}
                    onChange={(e) =>
                      updateLineItem(index, 'description', e.target.value)
                    }
                    className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="Description"
                  />
                </div>
                <div className="sm:col-span-2">
                  <input
                    type="number"
                    required
                    min="1"
                    step="1"
                    value={item.quantity}
                    onChange={(e) =>
                      updateLineItem(index, 'quantity', parseInt(e.target.value) || 0)
                    }
                    className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="Qty"
                  />
                </div>
                <div className="sm:col-span-2">
                  <input
                    type="number"
                    required
                    min="0"
                    step="0.01"
                    value={item.unit_price || ''}
                    onChange={(e) =>
                      updateLineItem(
                        index,
                        'unit_price',
                        parseFloat(e.target.value) || 0
                      )
                    }
                    className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="0.00"
                  />
                </div>
                <div className="sm:col-span-2">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.tax_rate || ''}
                    onChange={(e) =>
                      updateLineItem(
                        index,
                        'tax_rate',
                        parseFloat(e.target.value) || 0
                      )
                    }
                    className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="0"
                  />
                </div>
                <div className="sm:col-span-1 flex items-center justify-center">
                  <button
                    type="button"
                    onClick={() => removeLineItem(index)}
                    disabled={lineItems.length <= 1}
                    className="p-2 text-gray-400 dark:text-gray-500 hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Totals */}
          <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-700">
            <div className="flex flex-col items-end gap-1">
              <div className="flex justify-between w-64">
                <span className="text-sm text-gray-500 dark:text-gray-400">Subtotal</span>
                <span className="text-sm text-gray-900 dark:text-gray-100">
                  {formatCurrency(totals.subtotal, currency)}
                </span>
              </div>
              {totals.tax > 0 && (
                <div className="flex justify-between w-64">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Tax</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {formatCurrency(totals.tax, currency)}
                  </span>
                </div>
              )}
              {totals.discount > 0 && (
                <div className="flex justify-between w-64">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Discount</span>
                  <span className="text-sm text-red-600">
                    -{formatCurrency(totals.discount, currency)}
                  </span>
                </div>
              )}
              <div className="flex justify-between w-64 pt-2 border-t border-gray-200 dark:border-gray-700 mt-1">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Total</span>
                <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {formatCurrency(totals.total, currency)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Notes & Payment Terms */}
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder="Any additional notes for the client..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Payment Terms
            </label>
            <textarea
              value={paymentTerms}
              onChange={(e) => setPaymentTerms(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder="e.g., Net 30, Due on receipt..."
            />
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Invoice'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/invoices')}
            className="px-6 py-2.5 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Cancel
          </button>
        </div>

        {createMutation.isError && (
          <p className="text-sm text-red-500">
            Failed to create invoice. Please check all fields and try again.
          </p>
        )}
      </form>
    </div>
  );
}
