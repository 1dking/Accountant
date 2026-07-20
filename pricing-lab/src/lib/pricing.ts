// Pure pricing/projection math for the simulator — kept free of React so it
// can be unit-tested directly. All model assumptions are demo-grade and
// documented inline; the tool projects scenarios, it does not report actuals.
import { TIERS, type Tier } from '../data'

export interface SimulatorConfig {
  prices: Record<Tier['key'], number>
  monthlySignups: number // new signups joining the funnel each month
  elasticity: number // 0 = price has no effect on conversion; higher = more sensitive
  addonAttach: number // 0..1 share of paying accounts buying ~$20/mo of add-ons
  expansionRate: number // 0..1 monthly expansion MRR as share of existing MRR
  months: number
}

export interface ProjectionPoint {
  month: number
  mrr: number
  customers: number
  byTier: Record<Tier['key'], number> // MRR per tier
}

export interface ProjectionResult {
  series: ProjectionPoint[]
  endingMrr: number
  arr: number
  blendedArpu: number
  monthlyNrr: number // e.g. 1.012
  annualNrr: number // monthlyNrr^12
  payingCustomers: number
}

const ADDON_BASKET = 20 // demo: average add-on spend for attached accounts

/**
 * Price-elastic conversion adjustment: at the baseline price the multiplier is
 * 1; raising price lowers conversion and vice versa, with `elasticity`
 * controlling sensitivity. Multiplier = (base/price)^elasticity, clamped.
 */
export function conversionMultiplier(basePrice: number, price: number, elasticity: number): number {
  if (basePrice <= 0 || price <= 0) return 1
  const raw = Math.pow(basePrice / price, elasticity)
  return Math.min(2.5, Math.max(0.2, raw))
}

export function defaultConfig(): SimulatorConfig {
  return {
    prices: Object.fromEntries(TIERS.map((t) => [t.key, t.price])) as Record<Tier['key'], number>,
    monthlySignups: 800,
    elasticity: 1,
    addonAttach: 0.25,
    expansionRate: 0.015,
    months: 12,
  }
}

export function project(cfg: SimulatorConfig): ProjectionResult {
  // customers per paid tier; starter tracked for funnel realism but contributes $0
  const customers: Record<Tier['key'], number> = { starter: 0, pro: 0, business: 0, enterprise: 0 }
  const expansionMrrByTier: Record<Tier['key'], number> = { starter: 0, pro: 0, business: 0, enterprise: 0 }
  const series: ProjectionPoint[] = []
  let lastNrr = 1

  for (let m = 1; m <= cfg.months; m++) {
    const startMrr = totalMrr(customers, expansionMrrByTier, cfg)

    let churnedMrr = 0
    let expandedMrr = 0

    for (const tier of TIERS) {
      // churn existing
      const churned = customers[tier.key] * tier.baseChurn
      customers[tier.key] -= churned
      const priceNow = cfg.prices[tier.key]
      churnedMrr += churned * priceNow
      // expansion on remaining base (paid tiers only)
      if (priceNow > 0) {
        const exp = (customers[tier.key] * priceNow + expansionMrrByTier[tier.key]) * cfg.expansionRate
        expansionMrrByTier[tier.key] += exp
        expandedMrr += exp
      }
      // churn a matching share of accumulated expansion MRR
      const expChurn = expansionMrrByTier[tier.key] * tier.baseChurn
      expansionMrrByTier[tier.key] -= expChurn
      churnedMrr += expChurn
      // new signups, price-adjusted
      const mult = tier.price > 0 ? conversionMultiplier(tier.price, priceNow, cfg.elasticity) : 1
      customers[tier.key] += cfg.monthlySignups * tier.baseMix * mult * payRate(tier)
    }

    const mrr = totalMrr(customers, expansionMrrByTier, cfg)
    const byTier = Object.fromEntries(
      TIERS.map((t) => [t.key, customers[t.key] * cfg.prices[t.key] + expansionMrrByTier[t.key]])
    ) as Record<Tier['key'], number>
    series.push({ month: m, mrr, customers: payingCount(customers), byTier })

    // NRR of the existing book: what $1 of start-of-month MRR became, ignoring new sales
    lastNrr = startMrr > 0 ? (startMrr - churnedMrr + expandedMrr) / startMrr : 1
  }

  const endingMrr = series[series.length - 1]?.mrr ?? 0
  const paying = payingCount(customers)
  return {
    series,
    endingMrr,
    arr: endingMrr * 12,
    blendedArpu: paying > 0 ? endingMrr / paying : 0,
    monthlyNrr: lastNrr,
    annualNrr: Math.pow(lastNrr, 12),
    payingCustomers: paying,
  }
}

/** Share of a tier's activated signups that end up paying (demo assumption). */
function payRate(tier: Tier): number {
  switch (tier.key) {
    case 'starter': return 0 // free tier pays nothing by definition
    case 'pro': return 0.42
    case 'business': return 0.5
    case 'enterprise': return 0.58
  }
}

function totalMrr(
  customers: Record<Tier['key'], number>,
  expansion: Record<Tier['key'], number>,
  cfg: SimulatorConfig
): number {
  let mrr = 0
  for (const t of TIERS) {
    mrr += customers[t.key] * cfg.prices[t.key] + expansion[t.key]
  }
  const paying = payingCount(customers)
  mrr += paying * cfg.addonAttach * ADDON_BASKET
  return mrr
}

function payingCount(customers: Record<Tier['key'], number>): number {
  return TIERS.filter((t) => t.price > 0).reduce((s, t) => s + customers[t.key], 0)
}

export const fmtUsd = (n: number): string =>
  '$' + Math.round(n).toLocaleString('en-US')

export const fmtPct = (n: number): string => (n * 100).toFixed(1) + '%'
