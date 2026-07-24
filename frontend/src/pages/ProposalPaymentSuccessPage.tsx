import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { CheckCircle2, Loader2, XCircle, AlertCircle } from 'lucide-react'
import { getProposalPaymentStatus, type ProposalPaymentStatus } from '@/api/proposals'

/**
 * Public post-checkout page (route /proposals/:id/paid). The payer is a
 * client, not a logged-in user, so this is deliberately outside the app
 * shell — sending them to the auth-gated proposal editor bounced them to
 * the login screen. On load it verifies the payment with Stripe (which also
 * marks the proposal paid, independent of the webhook).
 */
export default function ProposalPaymentSuccessPage() {
  const { id } = useParams<{ id: string }>()
  const [search] = useSearchParams()
  const cancelled = search.get('status') === 'cancelled'

  const [state, setState] = useState<'loading' | 'paid' | 'pending' | 'error'>(
    cancelled ? 'pending' : 'loading'
  )
  const [info, setInfo] = useState<ProposalPaymentStatus | null>(null)

  useEffect(() => {
    if (!id || cancelled) return
    let active = true
    getProposalPaymentStatus(id)
      .then((res) => {
        if (!active) return
        setInfo(res.data)
        setState(res.data.paid ? 'paid' : 'pending')
      })
      .catch(() => active && setState('error'))
    return () => {
      active = false
    }
  }, [id, cancelled])

  const money = info ? `${info.currency} ${info.amount.toFixed(2)}` : ''

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <div className="max-w-sm w-full text-center bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-8 shadow-sm">
        {state === 'loading' && (
          <>
            <Loader2 className="w-10 h-10 text-blue-600 mx-auto mb-4 animate-spin" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Confirming your payment…
            </h1>
          </>
        )}

        {state === 'paid' && (
          <>
            <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Payment received</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Thank you! Your payment of <span className="font-medium">{money}</span> for{' '}
              <span className="font-medium">{info?.title}</span> is confirmed.
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
              A receipt has been emailed to you by Stripe. You can close this page.
            </p>
          </>
        )}

        {state === 'pending' && !cancelled && (
          <>
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Payment is processing
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              We haven’t received final confirmation from Stripe yet. If you completed payment, it
              will update shortly — no need to pay again.
            </p>
          </>
        )}

        {cancelled && (
          <>
            <XCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Payment cancelled
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              You closed the checkout before paying.
            </p>
            {id && (
              <a
                href={`/proposals/${id}/payment`}
                className="inline-block mt-5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Try payment again
              </a>
            )}
          </>
        )}

        {state === 'error' && (
          <>
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Couldn’t confirm payment
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              If you completed the payment, your receipt from Stripe is the confirmation. Please
              contact us if you have any questions.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
