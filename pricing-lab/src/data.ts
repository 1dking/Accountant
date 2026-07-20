// O-Brain's REAL pricing structure (from platform settings), plus a
// clearly-synthetic demo cohort for the analytics views. Everything derived
// from the demo cohort is labeled "Demo dataset" in the UI — no real customer
// numbers exist in this tool.

export interface Tier {
  key: 'starter' | 'pro' | 'business' | 'enterprise'
  name: string
  price: number // monthly USD
  quotas: { pages: number; storageGb: number; aiMessages: number }
  baseMix: number // share of new signups landing on this tier (demo assumption)
  baseChurn: number // monthly churn rate (demo assumption)
}

export const TIERS: Tier[] = [
  { key: 'starter', name: 'Starter', price: 0, quotas: { pages: 3, storageGb: 1, aiMessages: 50 }, baseMix: 0.62, baseChurn: 0.06 },
  { key: 'pro', name: 'Pro', price: 29, quotas: { pages: 25, storageGb: 10, aiMessages: 500 }, baseMix: 0.25, baseChurn: 0.03 },
  { key: 'business', name: 'Business', price: 79, quotas: { pages: 100, storageGb: 50, aiMessages: 2000 }, baseMix: 0.1, baseChurn: 0.02 },
  { key: 'enterprise', name: 'Enterprise', price: 199, quotas: { pages: 400, storageGb: 200, aiMessages: 10000 }, baseMix: 0.03, baseChurn: 0.01 },
]

export const ADDONS = [
  { key: 'sms', name: 'SMS credits (500)', price: 15 },
  { key: 'domain', name: 'Custom domain', price: 9 },
  { key: 'whitelabel', name: 'White-label', price: 49 },
  { key: 'aiUnlimited', name: 'Unlimited AI messages', price: 19 },
]

export interface ModuleStat {
  module: string
  category: string
  adoption: number // % of active accounts using it weekly (demo)
  retentionLift: number // pp difference in 6-mo retention, users vs non-users (demo)
  expansionLift: number // pp difference in upgrade rate (demo)
}

// Demo dataset — synthetic, directionally shaped by which modules are stickiest
// in products of this type. NOT measured customer data.
export const MODULE_STATS: ModuleStat[] = [
  { module: 'Contacts', category: 'CRM', adoption: 92, retentionLift: 11, expansionLift: 4 },
  { module: 'Invoices', category: 'Sales', adoption: 78, retentionLift: 18, expansionLift: 9 },
  { module: 'Phone & Dialer', category: 'Comms', adoption: 54, retentionLift: 22, expansionLift: 12 },
  { module: 'Cashbook', category: 'Accounting', adoption: 61, retentionLift: 19, expansionLift: 7 },
  { module: 'Proposals', category: 'Sales', adoption: 44, retentionLift: 15, expansionLift: 11 },
  { module: 'Meetings + AI Notes', category: 'Meetings', adoption: 47, retentionLift: 17, expansionLift: 10 },
  { module: 'Workflows', category: 'Automation', adoption: 38, retentionLift: 24, expansionLift: 14 },
  { module: 'Website Builder', category: 'Content', adoption: 33, retentionLift: 9, expansionLift: 8 },
  { module: 'Forms + Webhook', category: 'Content', adoption: 41, retentionLift: 13, expansionLift: 6 },
  { module: 'Inbox', category: 'Comms', adoption: 58, retentionLift: 12, expansionLift: 5 },
  { module: 'Drive', category: 'Storage', adoption: 66, retentionLift: 8, expansionLift: 3 },
  { module: 'Docs/Sheets/Slides', category: 'Office', adoption: 29, retentionLift: 7, expansionLift: 4 },
  { module: 'AI Chat', category: 'AI', adoption: 49, retentionLift: 16, expansionLift: 13 },
  { module: 'Coach & Intelligence', category: 'AI', adoption: 21, retentionLift: 20, expansionLift: 15 },
  { module: 'Client Portal', category: 'Admin', adoption: 26, retentionLift: 14, expansionLift: 9 },
]

// Demo funnel per tier: visitors → signups → activated → paying → expanded
export interface FunnelStage {
  stage: string
  starter: number
  pro: number
  business: number
  enterprise: number
}

export const FUNNEL: FunnelStage[] = [
  { stage: 'Visitors', starter: 12000, pro: 12000, business: 12000, enterprise: 12000 },
  { stage: 'Signups', starter: 1480, pro: 610, business: 240, enterprise: 70 },
  { stage: 'Activated', starter: 820, pro: 430, business: 185, enterprise: 58 },
  { stage: 'Paying', starter: 0, pro: 260, business: 121, enterprise: 41 },
  { stage: 'Expanded', starter: 0, pro: 74, business: 46, enterprise: 19 },
]

// Demo monthly revenue history (Jan–Jun 2026), MRR by tier + add-ons
export interface RevenueMonth {
  month: string
  starter: number
  pro: number
  business: number
  enterprise: number
  addons: number
}

export const REVENUE_HISTORY: RevenueMonth[] = [
  { month: 'Jan', starter: 0, pro: 3480, business: 3160, enterprise: 1990, addons: 610 },
  { month: 'Feb', starter: 0, pro: 4060, business: 3555, enterprise: 2189, addons: 720 },
  { month: 'Mar', starter: 0, pro: 4640, business: 4029, enterprise: 2388, addons: 866 },
  { month: 'Apr', starter: 0, pro: 5510, business: 4661, enterprise: 2985, addons: 1010 },
  { month: 'May', starter: 0, pro: 6293, business: 5451, enterprise: 3184, addons: 1187 },
  { month: 'Jun', starter: 0, pro: 7250, business: 6320, enterprise: 3781, addons: 1394 },
]

// Value-metric candidates: for a sample of demo accounts, usage vs paid tier
export interface AccountPoint {
  id: number
  tier: Tier['key']
  pagesPublished: number
  aiMessages: number
  storageGb: number
  seats: number
  activeClients: number
  paymentsProcessedUSD: number // GMV flowing through invoices/payments
  mrr: number
  // Outcome fields ("value delivered") used to score value-metric candidates
  retained6mo: boolean
  expansionMrr: number
}

function mulberry32(seed: number) {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const ACCOUNTS: AccountPoint[] = (() => {
  const rand = mulberry32(0xc0ffee)
  const out: AccountPoint[] = []
  const shape: Array<[Tier['key'], number, number, number, number, number]> = [
    // tier, count, pages μ, aiMsgs μ, storage μ, seats μ
    ['starter', 60, 1.6, 28, 0.4, 1.2],
    ['pro', 45, 11, 260, 4.2, 2.6],
    ['business', 25, 38, 900, 18, 6.5],
    ['enterprise', 10, 120, 3800, 70, 18],
  ]
  // Per-tier bases for the two business-outcome metrics. Both are drawn with a
  // power-law multiplier (few whales, long tail) and correlated with account
  // value: bigger tiers process more clients and more money.
  const CLIENT_BASE: Record<Tier['key'], number> = { starter: 4, pro: 16, business: 55, enterprise: 210 }
  const GMV_BASE: Record<Tier['key'], number> = { starter: 900, pro: 8500, business: 46000, enterprise: 240000 }

  let id = 1
  for (const [tier, count, pages, ai, storage, seats] of shape) {
    const price = TIERS.find((t) => t.key === tier)!.price
    for (let i = 0; i < count; i++) {
      const jitter = () => 0.35 + rand() * 1.5
      // Power-law draw in [1, 8]: Pareto-ish tail so a handful of accounts
      // dominate client count and GMV, as in real payment volume data.
      const plaw = Math.min(8, Math.pow(1 - rand(), -0.8))
      const activeClients = Math.max(1, Math.round(CLIENT_BASE[tier] * plaw * (0.45 + rand())))
      const paymentsProcessedUSD = Math.round(GMV_BASE[tier] * plaw * (0.4 + rand() * 1.4))
      // Outcomes are seeded to depend on realized business value (clients,
      // GMV) more than on raw usage — that is the structure the fit score is
      // supposed to recover, demonstrating the METHOD on synthetic data.
      const retainProb = Math.min(
        0.95,
        0.4 + 0.13 * Math.log10(1 + paymentsProcessedUSD / 500) + 0.005 * Math.min(40, activeClients)
      )
      const retained6mo = rand() < retainProb
      const expansionMrr =
        price > 0 ? Math.round(price * (activeClients / (CLIENT_BASE[tier] + 1)) * rand() * 0.5 * 100) / 100 : 0
      out.push({
        id: id++,
        tier,
        pagesPublished: Math.round(pages * jitter()),
        aiMessages: Math.round(ai * jitter()),
        storageGb: Math.round(storage * jitter() * 10) / 10,
        seats: Math.max(1, Math.round(seats * jitter())),
        activeClients,
        paymentsProcessedUSD,
        mrr: price,
        retained6mo,
        expansionMrr,
      })
    }
  }
  return out
})()

export const TIER_COLORS: Record<Tier['key'], string> = {
  starter: '#64748b',
  pro: '#8b5cf6',
  business: '#22d3ee',
  enterprise: '#f59e0b',
}
