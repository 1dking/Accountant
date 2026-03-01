import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Send,
  Download,
  Trash2,
  CreditCard,
  X,
  Mail,
  Link,
  MessageSquare,
  Bell,
} from 'lucide-react';
import {
  getInvoice,
  sendInvoice,
  deleteInvoice,
  recordPayment,
  downloadInvoicePdf,
} from '@/api/invoices';
import {
  sendInvoiceEmail,
  createPaymentLink,
  sendPaymentReminderEmail,
  sendInvoiceSms,
} from '@/api/integrations';
import ShareLinkDialog from '@/components/documents/ShareLinkDialog';
import { useAuthStore } from '@/stores/authStore';
import { INVOICE_STATUSES, PAYMENT_METHODS } from '@/lib/constants';
import { formatDate } from '@/lib/utils';
import type { PaymentData } from '@/api/invoices';

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';

  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [paymentData, setPaymentData] = useState<PaymentData>({
    amount: 0,
    date: new Date().toISOString().split('T')[0],
    payment_method: 'bank_transfer',
    reference: '',
    notes: '',
  });
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [showShareDialog, setShowShareDialog] = useState(false);

  const showActionMsg = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(''), 4000);
  };

  const invoiceQuery = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => getInvoice(id!),
    enabled: !!id,
  });

  const sendMutation = useMutation({
    mutationFn: () => sendInvoice(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteInvoice(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
      navigate('/invoices');
    },
  });

  const paymentMutation = useMutation({
    mutationFn: (data: PaymentData) => recordPayment(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoice-stats'] });
      setShowPaymentForm(false);
      setPaymentData({
        amount: 0,
        date: new Date().toISOString().split('T')[0],
        payment_method: 'bank_transfer',
        reference: '',
        notes: '',
      });
    },
  });

  const emailMutation = useMutation({
    mutationFn: () => sendInvoiceEmail({ invoice_id: id! }),
    onSuccess: () => showActionMsg('Invoice email sent!'),
    onError: () => showActionMsg('Failed to send email. Check SMTP settings.'),
  });

  const paymentLinkMutation = useMutation({
    mutationFn: () => createPaymentLink(id!),
    onSuccess: (data) => {
      const url = data.data.payment_url;
      navigator.clipboard.writeText(url);
      showActionMsg('Payment link copied to clipboard!');
    },
    onError: () => showActionMsg('Failed to create payment link. Check Stripe settings.'),
  });

  const reminderMutation = useMutation({
    mutationFn: () => sendPaymentReminderEmail({ invoice_id: id! }),
    onSuccess: () => showActionMsg('Reminder email sent!'),
    onError: () => showActionMsg('Failed to send reminder.'),
  });

  const smsMutation = useMutation({
    mutationFn: () => sendInvoiceSms({ invoice_id: id! }),
    onSuccess: () => showActionMsg('SMS sent!'),
    onError: () => showActionMsg('Failed to send SMS. Check Twilio settings.'),
  });

  if (invoiceQuery.isLoading) {
    return (
      <div className="p-6">
        <p className="text-gray-400">Loading invoice...</p>
      </div>
    );
  }

  if (invoiceQuery.isError || !invoiceQuery.data) {
    return (
      <div className="p-6">
        <p className="text-red-500">Failed to load invoice.</p>
        <button
          onClick={() => navigate('/invoices')}
          className="mt-2 text-blue-600 hover:underline"
        >
          Back to Invoices
        </button>
      </div>
    );
  }

  const invoice = invoiceQuery.data.data;
  const statusInfo = INVOICE_STATUSES.find((s) => s.value === invoice.status);
  const currency = invoice.currency || 'USD';

  const subtotal = invoice.line_items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price,
    0
  );
  const taxTotal = invoice.line_items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price * ((item.tax_rate ?? 0) / 100),
    0
  );
  const discountAmount = invoice.discount_amount ?? 0;
  const total = subtotal + taxTotal - discountAmount;

  const totalPaid = (invoice.payments ?? []).reduce(
    (sum, p) => sum + p.amount,
    0
  );
  const balanceDue = total - totalPaid;

  const isDraft = invoice.status === 'draft';
  const canRecordPayment =
    invoice.status === 'sent' ||
    invoice.status === 'viewed' ||
    invoice.status === 'partially_paid';

  const handleDownloadPdf = async () => {
    try {
      await downloadInvoicePdf(id!, invoice?.invoice_number);
    } catch {
      showActionMsg('Failed to download PDF.');
    }
  };

  const handleRecordPayment = (e: React.FormEvent) => {
    e.preventDefault();
    paymentMutation.mutate(paymentData);
  };

  return (
    <div className="p-6">
      {/* Back Button & Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/invoices')}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-700 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Invoices</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-gray-900">
                {invoice.invoice_number}
              </h1>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusInfo?.color ?? 'bg-gray-100 text-gray-700'}`}
              >
                {statusInfo?.label ?? invoice.status}
              </span>
            </div>
            <p className="text-gray-500 mt-1">
              {invoice.contact?.company_name}
              {invoice.contact?.email && (
                <span className="text-gray-400"> &middot; {invoice.contact.email}</span>
              )}
            </p>
          </div>

          {/* Actions */}
          {canEdit && (
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={handleDownloadPdf}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download PDF
              </button>

              {isDraft && (
                <button
                  onClick={() => sendMutation.mutate()}
                  disabled={sendMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  {sendMutation.isPending ? 'Sending...' : 'Send Invoice'}
                </button>
              )}

              {canRecordPayment && (
                <button
                  onClick={() => setShowPaymentForm(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  <CreditCard className="w-4 h-4" />
                  Record Payment
                </button>
              )}

              <button
                onClick={() => emailMutation.mutate()}
                disabled={emailMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                title="Email invoice with PDF"
              >
                <Mail className="w-4 h-4" />
                Email
              </button>

              <button
                onClick={() => paymentLinkMutation.mutate()}
                disabled={paymentLinkMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                title="Create Stripe payment link"
              >
                <Link className="w-4 h-4" />
                Payment Link
              </button>

              <button
                onClick={() => setShowShareDialog(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                title="Create shareable public link"
              >
                <Link className="w-4 h-4" />
                Share Link
              </button>

              {(invoice.status === 'overdue' || invoice.status === 'sent') && (
                <button
                  onClick={() => reminderMutation.mutate()}
                  disabled={reminderMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm border border-amber-200 text-amber-700 rounded-lg hover:bg-amber-50 transition-colors"
                  title="Send payment reminder"
                >
                  <Bell className="w-4 h-4" />
                  Remind
                </button>
              )}

              <button
                onClick={() => smsMutation.mutate()}
                disabled={smsMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
                title="Send invoice via SMS"
              >
                <MessageSquare className="w-4 h-4" />
                SMS
              </button>

              {isDraft && (
                <button
                  onClick={() => setDeleteConfirm(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex items-center justify-between">
          <p className="text-sm text-red-700">
            Are you sure you want to delete this invoice? This action cannot be undone.
          </p>
          <div className="flex items-center gap-2 ml-4">
            <button
              onClick={() => setDeleteConfirm(false)}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      )}

      {/* Action message */}
      {actionMsg && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-sm text-blue-700">
          {actionMsg}
        </div>
      )}

      {/* Invoice Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Issue Date</h3>
          <p className="text-gray-900">{formatDate(invoice.issue_date)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Due Date</h3>
          <p className="text-gray-900">{formatDate(invoice.due_date)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Balance Due</h3>
          <p className="text-2xl font-semibold text-gray-900">
            {formatCurrency(balanceDue, currency)}
          </p>
        </div>
      </div>

      {/* Line Items Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-lg font-medium text-gray-900">Line Items</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-5 py-3 text-gray-500 font-medium">Description</th>
              <th className="text-right px-5 py-3 text-gray-500 font-medium">Qty</th>
              <th className="text-right px-5 py-3 text-gray-500 font-medium">Unit Price</th>
              <th className="text-right px-5 py-3 text-gray-500 font-medium">Tax %</th>
              <th className="text-right px-5 py-3 text-gray-500 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {invoice.line_items.map((item, index) => {
              const lineSubtotal = item.quantity * item.unit_price;
              const lineTax = lineSubtotal * ((item.tax_rate ?? 0) / 100);
              const lineTotal = lineSubtotal + lineTax;
              return (
                <tr key={index} className="border-b border-gray-50">
                  <td className="px-5 py-3 text-gray-900">{item.description}</td>
                  <td className="px-5 py-3 text-right text-gray-700">{item.quantity}</td>
                  <td className="px-5 py-3 text-right text-gray-700">
                    {formatCurrency(item.unit_price, currency)}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500">
                    {item.tax_rate ? `${item.tax_rate}%` : '—'}
                  </td>
                  <td className="px-5 py-3 text-right font-medium text-gray-900">
                    {formatCurrency(lineTotal, currency)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Totals */}
        <div className="border-t border-gray-100 px-5 py-4">
          <div className="flex flex-col items-end gap-1">
            <div className="flex justify-between w-64">
              <span className="text-sm text-gray-500">Subtotal</span>
              <span className="text-sm text-gray-900">{formatCurrency(subtotal, currency)}</span>
            </div>
            {taxTotal > 0 && (
              <div className="flex justify-between w-64">
                <span className="text-sm text-gray-500">Tax</span>
                <span className="text-sm text-gray-900">{formatCurrency(taxTotal, currency)}</span>
              </div>
            )}
            {discountAmount > 0 && (
              <div className="flex justify-between w-64">
                <span className="text-sm text-gray-500">Discount</span>
                <span className="text-sm text-red-600">
                  -{formatCurrency(discountAmount, currency)}
                </span>
              </div>
            )}
            <div className="flex justify-between w-64 pt-2 border-t border-gray-200 mt-1">
              <span className="text-sm font-medium text-gray-900">Total</span>
              <span className="text-sm font-semibold text-gray-900">
                {formatCurrency(total, currency)}
              </span>
            </div>
            {totalPaid > 0 && (
              <>
                <div className="flex justify-between w-64">
                  <span className="text-sm text-gray-500">Paid</span>
                  <span className="text-sm text-green-600">
                    -{formatCurrency(totalPaid, currency)}
                  </span>
                </div>
                <div className="flex justify-between w-64 pt-1 border-t border-gray-200">
                  <span className="text-sm font-medium text-gray-900">Balance Due</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {formatCurrency(balanceDue, currency)}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Notes & Payment Terms */}
      {(invoice.notes || invoice.payment_terms) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {invoice.notes && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-medium text-gray-500 mb-2">Notes</h3>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{invoice.notes}</p>
            </div>
          )}
          {invoice.payment_terms && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="text-sm font-medium text-gray-500 mb-2">Payment Terms</h3>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{invoice.payment_terms}</p>
            </div>
          )}
        </div>
      )}

      {/* Payment History */}
      {invoice.payments && invoice.payments.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden mb-6">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-lg font-medium text-gray-900">Payment History</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-3 text-gray-500 font-medium">Date</th>
                <th className="text-left px-5 py-3 text-gray-500 font-medium">Method</th>
                <th className="text-left px-5 py-3 text-gray-500 font-medium">Reference</th>
                <th className="text-right px-5 py-3 text-gray-500 font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {invoice.payments.map((payment, index) => {
                const methodInfo = PAYMENT_METHODS.find(
                  (m) => m.value === payment.payment_method
                );
                return (
                  <tr key={index} className="border-b border-gray-50">
                    <td className="px-5 py-3 text-gray-900">{formatDate(payment.date)}</td>
                    <td className="px-5 py-3 text-gray-700">
                      {methodInfo?.label ?? payment.payment_method ?? '—'}
                    </td>
                    <td className="px-5 py-3 text-gray-500">{payment.reference || '—'}</td>
                    <td className="px-5 py-3 text-right font-medium text-green-600">
                      {formatCurrency(payment.amount, currency)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Record Payment Form */}
      {showPaymentForm && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Record Payment</h2>
            <button
              onClick={() => setShowPaymentForm(false)}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <form onSubmit={handleRecordPayment} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Amount <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={balanceDue}
                  required
                  value={paymentData.amount || ''}
                  onChange={(e) =>
                    setPaymentData({ ...paymentData, amount: parseFloat(e.target.value) || 0 })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder={`Max: ${formatCurrency(balanceDue, currency)}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date <span className="text-red-500">*</span>
                </label>
                <input
                  type="date"
                  required
                  value={paymentData.date}
                  onChange={(e) =>
                    setPaymentData({ ...paymentData, date: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Payment Method
                </label>
                <select
                  value={paymentData.payment_method}
                  onChange={(e) =>
                    setPaymentData({ ...paymentData, payment_method: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {PAYMENT_METHODS.map((method) => (
                    <option key={method.value} value={method.value}>
                      {method.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reference
                </label>
                <input
                  type="text"
                  value={paymentData.reference}
                  onChange={(e) =>
                    setPaymentData({ ...paymentData, reference: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Check #1234"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <textarea
                value={paymentData.notes}
                onChange={(e) =>
                  setPaymentData({ ...paymentData, notes: e.target.value })
                }
                rows={2}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                placeholder="Optional payment notes..."
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={paymentMutation.isPending || paymentData.amount <= 0}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm"
              >
                {paymentMutation.isPending ? 'Recording...' : 'Record Payment'}
              </button>
              <button
                type="button"
                onClick={() => setShowPaymentForm(false)}
                className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
            {paymentMutation.isError && (
              <p className="text-sm text-red-500">
                Failed to record payment. Please try again.
              </p>
            )}
          </form>
        </div>
      )}

      <ShareLinkDialog
        isOpen={showShareDialog}
        resourceType="invoice"
        resourceId={id!}
        onClose={() => setShowShareDialog(false)}
      />
    </div>
  );
}
