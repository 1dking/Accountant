import { useState } from 'react'
import { useParams } from 'react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getPublicDocument, acceptEstimate, payPublicDocument } from '@/api/public'
import type { PaymentIntentResponse } from '@/api/public'
import PaymentForm from '@/components/public/PaymentForm'
import SignaturePad from '@/components/public/SignaturePad'
import { CheckCircle, Loader2, AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { uiLocale } from '@/lib/utils'

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat(uiLocale(), { style: 'currency', currency }).format(amount)

export default function PublicDocumentPage() {
  const { t } = useTranslation('ui')
  const { token } = useParams<{ token: string }>()
  const [signatureData, setSignatureData] = useState<string | null>(null)
  const [signerName, setSignerName] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [paymentData, setPaymentData] = useState<PaymentIntentResponse | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['public-document', token],
    queryFn: () => getPublicDocument(token!),
    enabled: !!token,
  })

  const acceptMutation = useMutation({
    mutationFn: () =>
      acceptEstimate(token!, {
        signature_data: signatureData!,
        signer_name: signerName,
      }),
    onSuccess: () => {
      setAccepted(true)
      refetch()
    },
  })

  const payMutation = useMutation({
    mutationFn: () => payPublicDocument(token!),
    onSuccess: (response) => {
      setPaymentData(response.data)
      setShowPaymentForm(true)
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
           {t('ui:PublicDocumentPage.linkNotFound')}
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
           {t('ui:PublicDocumentPage.thisLinkMayHaveExpired')}
          </p>
        </div>
      </div>
    )
  }

  const { document: doc, company, actions, is_signed, stripe_configured } = data.data
  const isEstimate = doc.type === 'estimate'
  const isInvoice = doc.type === 'invoice'

  const subtotal = doc.line_items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price,
    0
  )
  const taxTotal = doc.line_items.reduce(
    (sum, item) =>
      sum + item.quantity * item.unit_price * ((item.tax_rate ?? 0) / 100),
    0
  )
  const discountAmount = doc.discount_amount ?? 0
  const total = subtotal + taxTotal - discountAmount

  const totalPaid = (doc.payments ?? []).reduce((sum, p) => sum + p.amount, 0)
  const balanceDue = total - totalPaid

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-800 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Document card */}
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border overflow-hidden">
          {/* Company header */}
          <div className="bg-gray-50 dark:bg-gray-950 border-b px-8 py-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                {company?.has_logo && (
                  <img
                    src="/api/settings/company/logo"
                    alt={t('ui:PublicDocumentPage.logo')}
                    className="h-12 w-auto object-contain"
                  />
                )}
                <div>
                  {company?.company_name && (
                    <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                      {company.company_name}
                    </h1>
                  )}
                  {(company?.address_line1 || company?.city || company?.state || company?.country) && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                      {[
                        company.address_line1,
                        [company.city, company.state].filter(Boolean).join(', '),
                        company.zip_code,
                        company.country,
                      ].filter(Boolean).join(', ')}
                    </p>
                  )}
                  {(company?.company_email || company?.company_phone) && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {[company.company_email, company.company_phone].filter(Boolean).join(' | ')}
                    </p>
                  )}
                </div>
              </div>
              <div className="text-right">
                <h2 className="text-2xl font-bold text-gray-400 dark:text-gray-500 uppercase">
                  {isEstimate ? t('ui:PublicDocumentPage.estimate') : t('ui:PublicDocumentPage.invoice')}
                </h2>
                <p className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">
                  {doc.number}
                </p>
              </div>
            </div>
          </div>

          <div className="px-8 py-6">
            {/* Bill-to + details */}
            <div className="grid grid-cols-2 gap-8 mb-8">
              <div>
                <h3 className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">
                  {isEstimate ? t('ui:PublicDocumentPage.preparedFor') : t('ui:PublicDocumentPage.billTo')}
                </h3>
                {doc.contact ? (
                  <div className="text-sm text-gray-700 dark:text-gray-300">
                    {doc.contact.company_name && (
                      <p className="font-medium">{doc.contact.company_name}</p>
                    )}
                    {doc.contact.contact_name && <p>{doc.contact.contact_name}</p>}
                    {doc.contact.email && (
                      <p className="text-gray-500 dark:text-gray-400">{doc.contact.email}</p>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 dark:text-gray-500">--</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-sm space-y-1">
                  <div className="flex justify-end gap-4">
                    <span className="text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.date')}</span>
                    <span className="text-gray-900 dark:text-gray-100">{doc.issue_date}</span>
                  </div>
                  {isEstimate && doc.expiry_date && (
                    <div className="flex justify-end gap-4">
                      <span className="text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.validUntil')}</span>
                      <span className="text-gray-900 dark:text-gray-100">{doc.expiry_date}</span>
                    </div>
                  )}
                  {isInvoice && doc.due_date && (
                    <div className="flex justify-end gap-4">
                      <span className="text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.dueDate')}</span>
                      <span className="text-gray-900 dark:text-gray-100">{doc.due_date}</span>
                    </div>
                  )}
                  <div className="flex justify-end gap-4">
                    <span className="text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.status')}</span>
                    <span className="text-gray-900 dark:text-gray-100 capitalize">
                      {doc.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Line items */}
            <table className="w-full text-sm mb-6">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:PublicDocumentPage.description')}
                  </th>
                  <th className="text-right py-3 font-medium text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.qty')}</th>
                  <th className="text-right py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:PublicDocumentPage.unitPrice')}
                  </th>
                  {doc.line_items.some((li) => li.tax_rate) && (
                    <th className="text-right py-3 font-medium text-gray-500 dark:text-gray-400">
                     {t('ui:PublicDocumentPage.tax')}
                    </th>
                  )}
                  <th className="text-right py-3 font-medium text-gray-500 dark:text-gray-400">
                   {t('ui:PublicDocumentPage.total')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {doc.line_items.map((item, i) => {
                  const lineSubtotal = item.quantity * item.unit_price
                  const lineTax =
                    lineSubtotal * ((item.tax_rate ?? 0) / 100)
                  const lineTotal = lineSubtotal + lineTax
                  return (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-700">
                      <td className="py-3 text-gray-900 dark:text-gray-100">{item.description}</td>
                      <td className="py-3 text-right text-gray-700 dark:text-gray-300">
                        {item.quantity}
                      </td>
                      <td className="py-3 text-right text-gray-700 dark:text-gray-300">
                        {formatCurrency(item.unit_price, doc.currency)}
                      </td>
                      {doc.line_items.some((li) => li.tax_rate) && (
                        <td className="py-3 text-right text-gray-500 dark:text-gray-400">
                          {item.tax_rate ? `${item.tax_rate}%` : '--'}
                        </td>
                      )}
                      <td className="py-3 text-right font-medium text-gray-900 dark:text-gray-100">
                        {formatCurrency(lineTotal, doc.currency)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Totals */}
            <div className="flex flex-col items-end gap-1 mb-8">
              <div className="flex justify-between w-56">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.subtotal')}</span>
                <span className="text-sm text-gray-900 dark:text-gray-100">
                  {formatCurrency(subtotal, doc.currency)}
                </span>
              </div>
              {taxTotal > 0 && (
                <div className="flex justify-between w-56">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.tax')}</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {formatCurrency(taxTotal, doc.currency)}
                  </span>
                </div>
              )}
              {discountAmount > 0 && (
                <div className="flex justify-between w-56">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.discount')}</span>
                  <span className="text-sm text-red-600">
                    -{formatCurrency(discountAmount, doc.currency)}
                  </span>
                </div>
              )}
              <div className="flex justify-between w-56 pt-2 border-t border-gray-300 dark:border-gray-600 mt-1">
                <span className="text-sm font-bold text-gray-900 dark:text-gray-100">{t('ui:PublicDocumentPage.total')}</span>
                <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                  {formatCurrency(total, doc.currency)}
                </span>
              </div>
              {isInvoice && totalPaid > 0 && (
                <>
                  <div className="flex justify-between w-56">
                    <span className="text-sm text-gray-500 dark:text-gray-400">{t('ui:PublicDocumentPage.paid')}</span>
                    <span className="text-sm text-green-600">
                      -{formatCurrency(totalPaid, doc.currency)}
                    </span>
                  </div>
                  <div className="flex justify-between w-56 pt-1 border-t">
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                     {t('ui:PublicDocumentPage.balanceDue')}
                    </span>
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                      {formatCurrency(balanceDue, doc.currency)}
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* Notes */}
            {doc.notes && (
              <div className="bg-gray-50 dark:bg-gray-950 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">{t('ui:PublicDocumentPage.notes')}</h3>
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {doc.notes}
                </p>
              </div>
            )}

            {/* Payment history */}
            {isInvoice && doc.payments && doc.payments.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                 {t('ui:PublicDocumentPage.paymentHistory')}
                </h3>
                <div className="space-y-1">
                  {doc.payments.map((p, i) => (
                    <div
                      key={i}
                      className="flex justify-between text-sm py-1.5 border-b border-gray-50"
                    >
                      <span className="text-gray-700 dark:text-gray-300">{p.date}</span>
                      <span className="text-gray-500 dark:text-gray-400 capitalize">
                        {(p.payment_method || '').replace('_', ' ')}
                      </span>
                      <span className="font-medium text-green-600">
                        {formatCurrency(p.amount, doc.currency)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Signed status */}
            {is_signed && doc.signed_by_name && (
              <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 rounded-lg p-4 mb-6 flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-600 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-green-800">
                   {t('ui:PublicDocumentPage.acceptedBy')} {doc.signed_by_name}
                  </p>
                  {doc.signed_at && (
                    <p className="text-xs text-green-600">
                      on {new Date(doc.signed_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Accept section (for estimates) */}
            {isEstimate &&
              actions.includes('accept') &&
              !is_signed &&
              !accepted && (
                <div className="border-t pt-6">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                   {t('ui:PublicDocumentPage.acceptThisEstimate')}
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                       {t('ui:PublicDocumentPage.yourName')}
                      </label>
                      <input
                        type="text"
                        value={signerName}
                        onChange={(e) => setSignerName(e.target.value)}
                        placeholder={t('ui:PublicDocumentPage.fullName')}
                        className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                       {t('ui:PublicDocumentPage.signature')}
                      </label>
                      <SignaturePad onSignatureChange={setSignatureData} />
                    </div>
                    <div className="flex gap-3">
                      <button
                        onClick={() => acceptMutation.mutate()}
                        disabled={
                          !signatureData ||
                          !signerName.trim() ||
                          acceptMutation.isPending
                        }
                        className="px-6 py-2.5 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {acceptMutation.isPending
                          ? t('ui:PublicDocumentPage.accepting')
                          : t('ui:PublicDocumentPage.acceptEstimate')}
                      </button>
                    </div>
                    {acceptMutation.isError && (
                      <p className="text-sm text-red-600">
                       {t('ui:PublicDocumentPage.failedToAcceptPleaseTry')}
                      </p>
                    )}
                  </div>
                </div>
              )}

            {/* Accepted confirmation */}
            {accepted && (
              <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 rounded-lg p-4 flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <p className="text-sm font-medium text-green-800">
                 {t('ui:PublicDocumentPage.estimateAcceptedSuccessfullyThankYou')}
                </p>
              </div>
            )}

            {/* Pay button (for invoices) */}
            {isInvoice && actions.includes('pay') && stripe_configured && balanceDue > 0 && (
              <div className="border-t pt-6">
                {showPaymentForm && paymentData ? (
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                     {t('ui:PublicDocumentPage.payment')}
                    </h3>
                    <PaymentForm
                      clientSecret={paymentData.client_secret}
                      publishableKey={paymentData.publishable_key}
                      connectedAccountId={paymentData.connected_account_id}
                      amount={paymentData.amount}
                      currency={paymentData.currency}
                      onSuccess={() => {
                        setShowPaymentForm(false)
                        refetch()
                      }}
                    />
                  </div>
                ) : (
                  <>
                    <button
                      onClick={() => payMutation.mutate()}
                      disabled={payMutation.isPending}
                      className="w-full px-6 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      {payMutation.isPending ? (
                        <span className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                         {t('ui:PublicDocumentPage.preparingPayment')}
                        </span>
                      ) : (
                        t('ui:PublicDocumentPage.payV0', { v0: formatCurrency(balanceDue, doc.currency) })
                      )}
                    </button>
                    {payMutation.isError && (
                      <p className="text-sm text-red-600 mt-2">
                       {t('ui:PublicDocumentPage.failedToInitiatePaymentPlease')}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        {company?.has_logo && (
          <div className="flex justify-center mt-6">
            <img
              src="/api/settings/company/logo"
              alt={t('ui:PublicDocumentPage.logo')}
              className="h-8 w-auto object-contain opacity-50"
            />
          </div>
        )}
      </div>
    </div>
  )
}
