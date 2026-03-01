import { useState, useMemo, type FormEvent } from 'react'
import { loadStripe } from '@stripe/stripe-js'
import {
  Elements,
  useStripe,
  useElements,
  PaymentElement,
} from '@stripe/react-stripe-js'
import { Loader2, CheckCircle, AlertCircle } from 'lucide-react'

interface PaymentFormProps {
  clientSecret: string
  publishableKey: string
  amount: number
  currency: string
  onSuccess: () => void
}

const formatCurrency = (amountCents: number, currency: string) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(
    amountCents / 100
  )

function CheckoutForm({
  amount,
  currency,
  onSuccess,
}: {
  amount: number
  currency: string
  onSuccess: () => void
}) {
  const stripe = useStripe()
  const elements = useElements()
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [succeeded, setSucceeded] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!stripe || !elements) return

    setProcessing(true)
    setError(null)

    const result = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: window.location.href,
      },
      redirect: 'if_required',
    })

    if (result.error) {
      setError(result.error.message ?? 'An unexpected error occurred.')
      setProcessing(false)
    } else {
      setSucceeded(true)
      setProcessing(false)
      onSuccess()
    }
  }

  if (succeeded) {
    return (
      <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 rounded-lg p-6 text-center">
        <CheckCircle className="h-10 w-10 text-green-600 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-green-800 dark:text-green-300 mb-1">
          Payment Successful
        </h3>
        <p className="text-sm text-green-700 dark:text-green-400">
          Thank you! Your payment of {formatCurrency(amount, currency)} has been
          received.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />

      {error && (
        <div className="flex items-center gap-2 mt-4 text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={!stripe || processing}
        className="w-full mt-6 px-6 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {processing ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </span>
        ) : (
          `Pay ${formatCurrency(amount, currency)}`
        )}
      </button>
    </form>
  )
}

export default function PaymentForm({
  clientSecret,
  publishableKey,
  amount,
  currency,
  onSuccess,
}: PaymentFormProps) {
  const stripePromise = useMemo(
    () => loadStripe(publishableKey),
    [publishableKey]
  )

  return (
    <Elements
      stripe={stripePromise}
      options={{
        clientSecret,
        appearance: {
          theme: 'stripe',
          variables: {
            colorPrimary: '#2563eb',
            borderRadius: '8px',
          },
        },
      }}
    >
      <CheckoutForm
        amount={amount}
        currency={currency}
        onSuccess={onSuccess}
      />
    </Elements>
  )
}
