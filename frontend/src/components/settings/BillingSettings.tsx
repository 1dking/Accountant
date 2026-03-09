import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Sparkles, Zap, Crown, Rocket, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'
import { platformAdminApi } from '@/api/platformAdmin'

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

  const { data: pricingData, isLoading } = useQuery({
    queryKey: ['billing-pricing'],
    queryFn: () => platformAdminApi.getPricing(),
  })

  const pricing = (pricingData as any)?.data ?? {}
  const p = (key: string) => Number(pricing[key] || 0)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Plan & Billing</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Choose the plan that fits your business.</p>
      </div>

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
            SAVE UP TO 20%
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
              <button
                className={cn(
                  'w-full py-2 rounded-lg text-sm font-medium transition-colors',
                  tier.popular
                    ? 'bg-purple-600 text-white hover:bg-purple-700'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600',
                )}
              >
                {tier.key === 'starter' ? 'Current Plan' : 'Upgrade'}
              </button>
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
