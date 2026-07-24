import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Check, Sparkles, Zap, Crown, Rocket, Brain, Loader2, CreditCard } from 'lucide-react'
import { cn } from '@/lib/utils'
import { platformAdminApi } from '@/api/platformAdmin'
import { billingApi } from '@/api/billing'
import { ApiClientError } from '@/api/client'

const PLAN_LABELS: Record<string, string> = {
  starter: 'Starter',
  pro: 'Professional',
  business: 'Business',
  enterprise: 'Enterprise',
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

/** One usage meter. A null limit means the plan is unlimited, so no bar. */
function UsageBar({
  label,
  used,
  limit,
  format = (n: number) => String(n),
  suffix = '',
}: {
  label: string
  used: number
  limit: number | null
  format?: (n: number) => string
  suffix?: string
}) {
  const unlimited = limit === null
  const pct = unlimited || limit === 0 ? 0 : Math.min(100, (used / limit) * 100)
  const atCap = !unlimited && used >= (limit ?? 0)
  const near = !unlimited && !atCap && pct >= 80

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
        <span className={cn(
          'text-xs font-semibold',
          atCap ? 'text-red-600 dark:text-red-400'
            : near ? 'text-amber-600 dark:text-amber-400'
              : 'text-gray-900 dark:text-white',
        )}>
          {format(used)}
          {unlimited ? ' / Unlimited' : ` / ${format(limit)}${suffix}`}
        </span>
      </div>
      {unlimited ? (
        <div className="h-1.5 rounded-full bg-gradient-to-r from-purple-400 to-blue-400 opacity-40" />
      ) : (
        <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              atCap ? 'bg-red-500' : near ? 'bg-amber-500' : 'bg-blue-600',
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      {atCap && (
        <p className="mt-1 text-[10px] text-red-600 dark:text-red-400">
          Limit reached — upgrade to continue.
        </p>
      )}
    </div>
  )
}

const PLAN_TIERS = [
  {
    key: 'starter',
    name: 'Starter',
    icon: Zap,
    color: 'blue',
    monthlyKey: 'plan_starter_price',
    annualKey: 'plan_starter_annual_price',
    features: ['1 GB storage', '3 pages', '50 O-Brain messages/mo', 'Basic accounting'],
  },
  {
    key: 'pro',
    name: 'Professional',
    icon: Crown,
    color: 'purple',
    monthlyKey: 'plan_pro_price',
    annualKey: 'plan_pro_annual_price',
    popular: true,
    features: ['10 GB storage', '25 pages', '500 O-Brain messages/mo', 'CRM + Invoicing', 'Email + SMS'],
  },
  {
    key: 'business',
    name: 'Business',
    icon: Rocket,
    color: 'orange',
    monthlyKey: 'plan_business_price',
    annualKey: 'plan_business_annual_price',
    features: ['50 GB storage', '100 pages', 'Unlimited O-Brain', 'Custom domain', 'White-label'],
  },
  {
    key: 'enterprise',
    name: 'Enterprise',
    icon: Sparkles,
    color: 'emerald',
    monthlyKey: 'plan_enterprise_price',
    annualKey: 'plan_enterprise_annual_price',
    features: ['Unlimited storage', 'Unlimited pages', 'O-Brain Coach', 'Priority support', 'API access'],
  },
]

const OBRAIN_TIERS = [
  {
    key: 'essential',
    name: 'Essential',
    monthlyKey: 'obrain_essential_price',
    annualKey: 'obrain_essential_annual_price',
    desc: '500 messages/mo, business tools, knowledge base',
  },
  {
    key: 'pro',
    name: 'Pro',
    monthlyKey: 'obrain_pro_price',
    annualKey: 'obrain_pro_annual_price',
    desc: 'Unlimited messages, all tools, file analysis, priority',
  },
  {
    key: 'coach',
    name: 'Coach',
    monthlyKey: 'obrain_coach_price',
    annualKey: 'obrain_coach_annual_price',
    desc: 'Everything in Pro + meeting analysis, monthly reports, deal tracking, nudges',
  },
]

export default function BillingSettings() {
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'annual'>('monthly')
  const [checkoutKey, setCheckoutKey] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const { data: pricingData, isLoading } = useQuery({
    queryKey: ['billing-pricing'],
    queryFn: () => platformAdminApi.getPricing(),
  })

  const pricing = pricingData?.data ?? {}
  const p = (key: string) => Number(pricing[key] || 0)

  const { data: subData } = useQuery({
    queryKey: ['billing-subscription'],
    queryFn: () => billingApi.getSubscription(),
  })
  const subscription = subData?.data

  const { data: usageData } = useQuery({
    queryKey: ['billing-usage'],
    queryFn: () => billingApi.getUsage(),
  })
  const usage = usageData?.data
  const currentPlan: string = subscription?.plan_key ?? 'starter'

  // Handle the Stripe Checkout return (success_url / cancel_url land here with query params)
  useEffect(() => {
    const subStatus = searchParams.get('sub')
    const sessionId = searchParams.get('session_id')
    if (!subStatus) return

    if (subStatus === 'success' && sessionId) {
      billingApi
        .verify(sessionId)
        .then((res) => {
          const plan = res?.data?.plan_key
          toast.success(plan ? `You're now on the ${PLAN_LABELS[plan] ?? plan} plan.` : 'Subscription activated.')
          queryClient.invalidateQueries({ queryKey: ['billing-subscription'] })
          queryClient.invalidateQueries({ queryKey: ['billing-usage'] })
        })
        .catch(() => toast.error('We could not confirm your subscription. If you were charged, contact support.'))
    } else if (subStatus === 'cancelled') {
      toast('Checkout cancelled — no changes made.')
    }
    // Strip the billing query params so a refresh doesn't re-verify
    const next = new URLSearchParams(searchParams)
    next.delete('sub')
    next.delete('session_id')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, queryClient])

  const checkoutMutation = useMutation({
    mutationFn: ({ planKey }: { planKey: string }) => billingApi.createCheckout(planKey, billingPeriod),
    onMutate: ({ planKey }) => setCheckoutKey(planKey),
    onSuccess: (res) => {
      const data = res?.data
      if (data?.checkout_url) {
        window.location.href = data.checkout_url
        return
      }
      // Free tier: plan switched server-side, no Stripe redirect
      toast.success('You\'re on the Starter plan.')
      queryClient.invalidateQueries({ queryKey: ['billing-subscription'] })
      queryClient.invalidateQueries({ queryKey: ['billing-usage'] })
      setCheckoutKey(null)
    },
    onError: (err) => {
      // Surface the real reason (e.g. misconfigured plan pricing) — the admin
      // needs to know what to fix, not just "try again".
      const msg = err instanceof ApiClientError ? err.error?.message : null
      toast.error(msg || 'Could not start checkout. Please try again.')
      setCheckoutKey(null)
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => billingApi.openPortal(),
    onSuccess: (res) => {
      const url = res?.data?.url
      if (url) window.location.href = url
      else toast.error('Billing portal is unavailable right now.')
    },
    onError: (err) => {
      const msg = err instanceof ApiClientError ? err.error?.message : null
      toast.error(msg || 'Could not open the billing portal.')
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Plan & Billing</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            You're currently on the{' '}
            <span className="font-semibold text-gray-900 dark:text-white">{PLAN_LABELS[currentPlan] ?? currentPlan}</span>{' '}
            plan{subscription?.billing_period ? ` (${subscription.billing_period})` : ''}.
          </p>
        </div>
        {subscription?.has_stripe_customer && (
          <button
            onClick={() => portalMutation.mutate()}
            disabled={portalMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-60"
          >
            {portalMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Manage billing
          </button>
        )}
      </div>

      {/* Usage against the current plan's caps */}
      {usage && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
            Your usage this billing period
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <UsageBar label="Published pages" used={usage.pages.used} limit={usage.pages.limit} />
            <UsageBar
              label="Storage"
              used={usage.storage.used}
              limit={usage.storage.limit}
              format={formatBytes}
            />
            <UsageBar
              label="O-Brain messages"
              used={usage.ai_messages.used}
              limit={usage.ai_messages.limit}
              suffix="/mo"
            />
          </div>
        </div>
      )}

      {/* Monthly / Annual toggle */}
      <div className="flex items-center justify-center gap-3">
        <span className={cn('text-sm font-medium', billingPeriod === 'monthly' ? 'text-gray-900 dark:text-white' : 'text-gray-400')}>
          Monthly
        </span>
        <button
          onClick={() => setBillingPeriod(billingPeriod === 'monthly' ? 'annual' : 'monthly')}
          className={cn(
            'relative w-12 h-6 rounded-full transition-colors',
            billingPeriod === 'annual' ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600',
          )}
        >
          <span className={cn(
            'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
            billingPeriod === 'annual' ? 'translate-x-6.5' : 'translate-x-0.5',
          )} />
        </button>
        <span className={cn('text-sm font-medium', billingPeriod === 'annual' ? 'text-gray-900 dark:text-white' : 'text-gray-400')}>
          Annual
        </span>
        {billingPeriod === 'annual' && (
          <span className="ml-1 text-[10px] font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">
            2 MONTHS FREE
          </span>
        )}
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {PLAN_TIERS.map((tier) => {
          const monthly = p(tier.monthlyKey)
          const annual = p(tier.annualKey)
          const price = billingPeriod === 'monthly' ? monthly : annual
          const Icon = tier.icon
          const savings = monthly > 0 ? Math.round(((monthly - annual) / monthly) * 100) : 0

          return (
            <div
              key={tier.key}
              className={cn(
                'relative rounded-xl border p-5 flex flex-col',
                tier.popular
                  ? 'border-purple-400 dark:border-purple-600 ring-2 ring-purple-200 dark:ring-purple-800'
                  : 'border-gray-200 dark:border-gray-700',
              )}
            >
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-purple-600 text-white text-[10px] font-bold px-3 py-0.5 rounded-full">
                  MOST POPULAR
                </div>
              )}
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                <h3 className="font-semibold text-gray-900 dark:text-white">{tier.name}</h3>
              </div>
              <div className="mb-4">
                <span className="text-3xl font-bold text-gray-900 dark:text-white">
                  ${price}
                </span>
                <span className="text-sm text-gray-500 dark:text-gray-400">/mo</span>
                {billingPeriod === 'annual' && (
                  <span className="block text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                    billed yearly (${annual * 12}/yr)
                  </span>
                )}
                {billingPeriod === 'annual' && savings > 0 && (
                  <span className="inline-block mt-1 text-[10px] font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-1.5 py-0.5 rounded">
                    Save {savings}%
                  </span>
                )}
              </div>
              <ul className="space-y-2 flex-1 mb-4">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                    <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
              {(() => {
                const isCurrent = tier.key === currentPlan
                const isBusy = checkoutMutation.isPending && checkoutKey === tier.key
                return (
                  <button
                    disabled={isCurrent || checkoutMutation.isPending}
                    onClick={() => checkoutMutation.mutate({ planKey: tier.key })}
                    className={cn(
                      'w-full py-2 rounded-lg text-sm font-medium transition-colors inline-flex items-center justify-center gap-2',
                      isCurrent
                        ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-default'
                        : tier.popular
                          ? 'bg-purple-600 text-white hover:bg-purple-700'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600',
                      checkoutMutation.isPending && !isBusy && 'opacity-60',
                    )}
                  >
                    {isBusy && <Loader2 className="w-4 h-4 animate-spin" />}
                    {isCurrent ? 'Current Plan' : tier.key === 'starter' ? 'Downgrade to free' : 'Choose plan'}
                  </button>
                )
              })()}
            </div>
          )
        })}
      </div>

      {/* O-Brain Add-ons */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-purple-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">O-Brain Add-ons</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {OBRAIN_TIERS.map((tier) => {
            const monthly = p(tier.monthlyKey)
            const annual = p(tier.annualKey)
            const price = billingPeriod === 'monthly' ? monthly : annual
            const savings = monthly > 0 ? Math.round(((monthly - annual) / monthly) * 100) : 0

            return (
              <div key={tier.key} className="rounded-xl border border-gray-200 dark:border-gray-700 p-5">
                <h4 className="font-semibold text-gray-900 dark:text-white mb-1">{tier.name}</h4>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">{tier.desc}</p>
                <div className="mb-3">
                  <span className="text-2xl font-bold text-gray-900 dark:text-white">${price}</span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">/mo</span>
                  {billingPeriod === 'annual' && savings > 0 && (
                    <span className="ml-2 text-[10px] font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-1.5 py-0.5 rounded">
                      Save {savings}%
                    </span>
                  )}
                </div>
                <button className="w-full py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                  Add to Plan
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
