import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Send,
  Trash2,
  FileText,
  CheckCircle,
  XCircle,
  Mail,
  Link,
} from 'lucide-react';
import {
  getEstimate,
  updateEstimate,
  deleteEstimate,
  convertEstimateToInvoice,
  sendEstimateEmail,
} from '@/api/estimates';
import ShareLinkDialog from '@/components/documents/ShareLinkDialog';
import { useAuthStore } from '@/stores/authStore';
import { ESTIMATE_STATUSES } from '@/lib/constants';
import { formatDate } from '@/lib/utils';

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

export default function EstimateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const canEdit = user?.role === 'admin' || user?.role === 'accountant';

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [showShareDialog, setShowShareDialog] = useState(false);

  const showActionMsg = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(''), 4000);
  };

  const estimateQuery = useQuery({
    queryKey: ['estimate', id],
    queryFn: () => getEstimate(id!),
    enabled: !!id,
  });

  const sendMutation = useMutation({
    mutationFn: () => updateEstimate(id!, { status: 'sent' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['estimate', id] });
      queryClient.invalidateQueries({ queryKey: ['estimates'] });
      showActionMsg('Estimate marked as sent.');
    },
  });

  const acceptMutation = useMutation({
    mutationFn: () => updateEstimate(id!, { status: 'accepted' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['estimate', id] });
      queryClient.invalidateQueries({ queryKey: ['estimates'] });
      showActionMsg('Estimate accepted.');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => updateEstimate(id!, { status: 'rejected' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['estimate', id] });
      queryClient.invalidateQueries({ queryKey: ['estimates'] });
      showActionMsg('Estimate rejected.');
    },
  });

  const convertMutation = useMutation({
    mutationFn: () => convertEstimateToInvoice(id!),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['estimate', id] });
      queryClient.invalidateQueries({ queryKey: ['estimates'] });
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      navigate(`/invoices/${response.data.id}`);
    },
  });

  const emailMutation = useMutation({
    mutationFn: () => sendEstimateEmail(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['estimate', id] });
      showActionMsg('Estimate email sent to client!');
    },
    onError: () => showActionMsg('Failed to send email. Check SMTP settings.'),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEstimate(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['estimates'] });
      navigate('/estimates');
    },
  });

  if (estimateQuery.isLoading) {
    return (
      <div className="p-6">
        <p className="text-gray-400 dark:text-gray-500">Loading estimate...</p>
      </div>
    );
  }

  if (estimateQuery.isError || !estimateQuery.data) {
    return (
      <div className="p-6">
        <p className="text-red-500">Failed to load estimate.</p>
        <button
          onClick={() => navigate('/estimates')}
          className="mt-2 text-blue-600 dark:text-blue-400 hover:underline"
        >
          Back to Estimates
        </button>
      </div>
    );
  }

  const estimate = estimateQuery.data.data;
  const statusInfo = ESTIMATE_STATUSES.find((s) => s.value === estimate.status);
  const currency = estimate.currency || 'USD';

  const subtotal = estimate.line_items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price,
    0
  );
  const taxTotal = estimate.line_items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price * ((item.tax_rate ?? 0) / 100),
    0
  );
  const discountAmount = estimate.discount_amount ?? 0;
  const total = subtotal + taxTotal - discountAmount;

  const isDraft = estimate.status === 'draft';
  const isSent = estimate.status === 'sent';
  const isAccepted = estimate.status === 'accepted';
  const isConverted = estimate.status === 'converted';
  const canConvert = (isSent || isAccepted) && !isConverted;

  return (
    <div className="p-6">
      {/* Back Button & Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/estimates')}
          className="flex items-center gap-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Estimates</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
                {estimate.estimate_number}
              </h1>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusInfo?.color ?? 'bg-gray-100 dark:bg-gray-800 text-gray-700'}`}
              >
                {statusInfo?.label ?? estimate.status}
              </span>
            </div>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              {estimate.contact?.company_name}
              {estimate.contact?.email && (
                <span className="text-gray-400 dark:text-gray-500"> &middot; {estimate.contact.email}</span>
              )}
            </p>
          </div>

          {/* Actions */}
          {canEdit && (
            <div className="flex items-center gap-2 flex-wrap">
              {isDraft && (
                <button
                  onClick={() => sendMutation.mutate()}
                  disabled={sendMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  {sendMutation.isPending ? 'Sending...' : 'Mark as Sent'}
                </button>
              )}

              {isSent && (
                <>
                  <button
                    onClick={() => acceptMutation.mutate()}
                    disabled={acceptMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    <CheckCircle className="w-4 h-4" />
                    {acceptMutation.isPending ? 'Accepting...' : 'Accept'}
                  </button>
                  <button
                    onClick={() => rejectMutation.mutate()}
                    disabled={rejectMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                    {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                  </button>
                </>
              )}

              {canConvert && (
                <button
                  onClick={() => convertMutation.mutate()}
                  disabled={convertMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  {convertMutation.isPending ? 'Converting...' : 'Convert to Invoice'}
                </button>
              )}

              {isConverted && estimate.converted_invoice_id && (
                <button
                  onClick={() => navigate(`/invoices/${estimate.converted_invoice_id}`)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm border border-purple-200 text-purple-700 rounded-lg hover:bg-purple-50 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  View Invoice
                </button>
              )}

              <button
                onClick={() => emailMutation.mutate()}
                disabled={emailMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                title="Email estimate to client"
              >
                <Mail className="w-4 h-4" />
                Email
              </button>

              <button
                onClick={() => setShowShareDialog(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                title="Create shareable link"
              >
                <Link className="w-4 h-4" />
                Share Link
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
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 rounded-xl p-4 mb-6 flex items-center justify-between">
          <p className="text-sm text-red-700">
            Are you sure you want to delete this estimate? This action cannot be undone.
          </p>
          <div className="flex items-center gap-2 ml-4">
            <button
              onClick={() => setDeleteConfirm(false)}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-white dark:bg-gray-900 transition-colors"
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
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 rounded-lg p-3 mb-6 text-sm text-blue-700">
          {actionMsg}
        </div>
      )}

      {/* Convert mutation error */}
      {convertMutation.isError && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 rounded-lg p-3 mb-6 text-sm text-red-700">
          Failed to convert estimate to invoice. Please try again.
        </div>
      )}

      {/* Estimate Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Issue Date</h3>
          <p className="text-gray-900 dark:text-gray-100">{formatDate(estimate.issue_date)}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Expiry Date</h3>
          <p className="text-gray-900 dark:text-gray-100">{formatDate(estimate.expiry_date)}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Total</h3>
          <p className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(estimate.total, currency)}
          </p>
        </div>
      </div>

      {/* Line Items Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">Line Items</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-700">
              <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Description</th>
              <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Qty</th>
              <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Unit Price</th>
              <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Tax %</th>
              <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {estimate.line_items.map((item, index) => {
              const lineSubtotal = item.quantity * item.unit_price;
              const lineTax = lineSubtotal * ((item.tax_rate ?? 0) / 100);
              const lineTotal = lineSubtotal + lineTax;
              return (
                <tr key={index} className="border-b border-gray-50">
                  <td className="px-5 py-3 text-gray-900 dark:text-gray-100">{item.description}</td>
                  <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">{item.quantity}</td>
                  <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">
                    {formatCurrency(item.unit_price, currency)}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-500 dark:text-gray-400">
                    {item.tax_rate ? `${item.tax_rate}%` : '--'}
                  </td>
                  <td className="px-5 py-3 text-right font-medium text-gray-900 dark:text-gray-100">
                    {formatCurrency(lineTotal, currency)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Totals */}
        <div className="border-t border-gray-100 dark:border-gray-700 px-5 py-4">
          <div className="flex flex-col items-end gap-1">
            <div className="flex justify-between w-64">
              <span className="text-sm text-gray-500 dark:text-gray-400">Subtotal</span>
              <span className="text-sm text-gray-900 dark:text-gray-100">{formatCurrency(subtotal, currency)}</span>
            </div>
            {taxTotal > 0 && (
              <div className="flex justify-between w-64">
                <span className="text-sm text-gray-500 dark:text-gray-400">Tax</span>
                <span className="text-sm text-gray-900 dark:text-gray-100">{formatCurrency(taxTotal, currency)}</span>
              </div>
            )}
            {discountAmount > 0 && (
              <div className="flex justify-between w-64">
                <span className="text-sm text-gray-500 dark:text-gray-400">Discount</span>
                <span className="text-sm text-red-600">
                  -{formatCurrency(discountAmount, currency)}
                </span>
              </div>
            )}
            <div className="flex justify-between w-64 pt-2 border-t border-gray-200 dark:border-gray-700 mt-1">
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Total</span>
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {formatCurrency(total, currency)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Notes */}
      {estimate.notes && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-5 mb-6">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Notes</h3>
          <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{estimate.notes}</p>
        </div>
      )}

      <ShareLinkDialog
        isOpen={showShareDialog}
        resourceType="estimate"
        resourceId={id!}
        onClose={() => setShowShareDialog(false)}
      />
    </div>
  );
}
