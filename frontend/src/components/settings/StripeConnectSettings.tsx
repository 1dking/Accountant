import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Trash2 } from 'lucide-react'
import { connectStripeAccount, getStripeConnectStatus, disconnectStripeAccount } from '@/api/integrations'
import { ApiClientError } from '@/api/client'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

export default function StripeConnectSettings() {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const handledRef = useRef(false)

  useEffect(() => {
    if (handledRef.current) return
    const connected = searchParams.get('connected')
    const pending = searchParams.get('pending')
    const error = searchParams.get('error')
    if (connected === 'true') {
      handledRef.current = true
      toast.success(t('ui:StripeConnectSettings.stripeAccountConnected'))
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    } else if (pending === 'true') {
      handledRef.current = true
      toast(t('ui:StripeConnectSettings.stripeOnboardingStartedFinishIt'))
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    } else if (error) {
      handledRef.current = true
      toast.error(t('ui:StripeConnectSettings.stripeConnectionFailedV0', { v0: decodeURIComponent(error) }))
      setSearchParams({ tab: 'stripe_connect' }, { replace: true })
    }
  }, [searchParams, queryClient, setSearchParams])

  const { data, isLoading } = useQuery({
    queryKey: ['stripe-connect-status'],
    queryFn: getStripeConnectStatus,
  })

  const connectMutation = useMutation({
    mutationFn: connectStripeAccount,
    onSuccess: (data) => {
      window.location.href = data.data.url
    },
    onError: (err: unknown) => {
      const message = err instanceof ApiClientError ? err.error.message : 'Failed to start Stripe onboarding'
      toast.error(message)
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: disconnectStripeAccount,
    onSuccess: () => {
      toast.success(t('ui:StripeConnectSettings.stripeAccountDisconnected'))
      queryClient.invalidateQueries({ queryKey: ['stripe-connect-status'] })
    },
  })

  const account = data?.data ?? null

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{t('ui:StripeConnectSettings.stripeConnect')}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
         {t('ui:StripeConnectSettings.connectYourOwnStripeAccount')}
        </p>
      </div>

      {!isLoading && !account && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-6 text-center">
          <CreditCard className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">
           {t('ui:StripeConnectSettings.noStripeAccountConnectedYet')}
          </p>
          <button
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <CreditCard className="w-4 h-4" />
            {connectMutation.isPending ? t('ui:StripeConnectSettings.connecting') : t('ui:StripeConnectSettings.connectStripeAccount')}
          </button>
        </div>
      )}

      {account && (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-500" />
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {account.stripe_account_id}
                </span>
                {account.charges_enabled ? (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                   {t('ui:StripeConnectSettings.activeAcceptingPayments')}
                  </span>
                ) : (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                   {t('ui:StripeConnectSettings.onboardingIncomplete')}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {account.onboarding_completed_at
                  ? t('ui:StripeConnectSettings.liveSinceV0', { v0: formatDate(account.onboarding_completed_at) })
                  : t('ui:StripeConnectSettings.finishOnboardingInStripeTo')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!account.charges_enabled && (
                <button
                  onClick={() => connectMutation.mutate()}
                  disabled={connectMutation.isPending}
                  className="flex items-center gap-1 px-2 py-1 text-sm text-blue-600 border border-blue-200 rounded hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50"
                >
                 {t('ui:StripeConnectSettings.continueOnboarding')}
                </button>
              )}
              <button
                onClick={() => { if (confirm(t('ui:StripeConnectSettings.disconnectYourStripeAccountClient'))) disconnectMutation.mutate() }}
                className="flex items-center gap-1 px-2 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50 dark:hover:bg-red-950"
              >
                <Trash2 className="w-3.5 h-3.5" />
               {t('ui:StripeConnectSettings.disconnect')}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-gray-50 dark:bg-gray-950 border rounded-lg p-4 text-sm text-gray-600 dark:text-gray-400">
        <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ui:StripeConnectSettings.howItWorks')}</h4>
        <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400">
          <li>{t('ui:StripeConnectSettings.connectAStripeExpressAccount')}</li>
          <li>{t('ui:StripeConnectSettings.onceActiveInvoiceAndProposal')}</li>
          <li>{t('ui:StripeConnectSettings.withoutAConnectedAccountPayments')}</li>
        </ul>
      </div>
    </div>
  )
}
