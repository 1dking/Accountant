// Synthetic demo cohort, reshaped into the spec's DataAdapter interface so it
// is structurally interchangeable with OBrainAdapter. Real price points
// (TIERS in ../data), synthetic everything else.
import { ACCOUNTS, MODULE_STATS } from '../data'
import type { Account, DataAdapter, LifecycleEvent, ModuleUsageRow, ValueMetricRow } from './types'

const DEMO_MONTH = '2026-06'

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

export class MockAdapter implements DataAdapter {
  readonly source = 'mock' as const

  async getAccounts(): Promise<Account[]> {
    return ACCOUNTS.map((a) => ({
      orgId: String(a.id),
      tier: a.tier,
      mrr: a.mrr,
      billingCycle: 'monthly',
      status: a.retained6mo ? 'active' : 'churned',
      activatedModules: [],
      whiteLabel: a.tier === 'business' || a.tier === 'enterprise' ? a.seats > 8 : false,
      signupDate: null,
      industry: null,
      teamSize: a.seats,
    }))
  }

  async getValueMetrics(): Promise<ValueMetricRow[]> {
    return ACCOUNTS.map((a) => ({
      orgId: String(a.id),
      month: DEMO_MONTH,
      activeClients: a.activeClients,
      paymentsProcessedUSD: a.paymentsProcessedUSD,
      aiMessages: a.aiMessages,
      voiceMinutes: 0,
      smsSegments: 0,
      storageGB: a.storageGb,
      publishedPages: a.pagesPublished,
      seatsUsed: a.seats,
      demoRetained6mo: a.retained6mo,
      demoExpansionMrr: a.expansionMrr,
      demoTier: a.tier,
    }))
  }

  async getLifecycleEvents(): Promise<LifecycleEvent[]> {
    const rand = mulberry32(0xfeed)
    const events: LifecycleEvent[] = []
    for (const a of ACCOUNTS) {
      const orgId = String(a.id)
      const signupDay = 1 + Math.floor(rand() * 25)
      events.push({
        event: 'account_signup', orgId,
        timestamp: `2026-0${1 + Math.floor(rand() * 5)}-${String(signupDay).padStart(2, '0')}T00:00:00Z`,
        properties: { teamSize: a.seats },
      })
      if (a.mrr > 0) {
        events.push({
          event: 'trial_converted', orgId,
          timestamp: `2026-06-${String(1 + Math.floor(rand() * 25)).padStart(2, '0')}T00:00:00Z`,
          properties: { toTier: a.tier, mrr: a.mrr },
        })
      }
      if (!a.retained6mo) {
        events.push({
          event: 'account_churned', orgId,
          timestamp: '2026-06-28T00:00:00Z',
          properties: { fromTier: a.tier },
        })
      }
    }
    return events
  }

  async getModuleUsage(): Promise<ModuleUsageRow[]> {
    const rand = mulberry32(0xd00d)
    const rows: ModuleUsageRow[] = []
    for (const stat of MODULE_STATS) {
      for (const a of ACCOUNTS) {
        if (rand() * 100 > stat.adoption) continue // this account doesn't use this module
        rows.push({
          orgId: String(a.id),
          module: stat.module,
          firstUsedDate: '2026-02-01T00:00:00Z',
          monthlyActiveCount: 1 + Math.floor(rand() * 6),
        })
      }
    }
    return rows
  }
}
