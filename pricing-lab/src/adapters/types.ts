// Shapes mirror OBRAIN_EVENT_SPEC.md §2-§4 exactly, so MockAdapter and
// OBrainAdapter are interchangeable. Fields the backend can't populate yet
// (no lifecycle events emitted this pass — see backend/app/events/service.py
// module docstring) are `| null` rather than defaulted to 0/false, so the UI
// can tell "real zero" apart from "not tracked yet."

export interface LifecycleEvent {
  event: string
  orgId: string
  timestamp: string
  properties: Record<string, unknown>
}

export type AccountStatus = 'trial' | 'active' | 'churned' | 'downgraded' | 'unknown'

export interface Account {
  orgId: string
  tier: string | null
  mrr: number | null
  billingCycle: string | null
  status: AccountStatus
  activatedModules: string[]
  whiteLabel: boolean
  signupDate: string | null
  industry: string | null
  teamSize: number | null
}

export interface ValueMetricRow {
  orgId: string
  month: string // YYYY-MM
  activeClients: number | null
  paymentsProcessedUSD: number
  aiMessages: number
  voiceMinutes: number
  smsSegments: number
  storageGB: number | null
  publishedPages: number | null
  seatsUsed: number | null
  // Demo-only enrichment (MockAdapter never leaves these undefined; real
  // OBrainAdapter rows always leave them undefined until lifecycle events —
  // spec §6 step 2 — exist). The Value-Metric Explorer's "fit" score checks
  // for these and degrades its outcome set honestly when they're absent,
  // rather than pretending retention/expansion data exists when it doesn't.
  demoRetained6mo?: boolean
  demoExpansionMrr?: number
  demoTier?: string
}

export interface ModuleUsageRow {
  orgId: string
  module: string
  firstUsedDate: string | null
  monthlyActiveCount: number
}

export type AdapterSource = 'mock' | 'obrain'

export interface DataAdapter {
  readonly source: AdapterSource
  getAccounts(): Promise<Account[]>
  getValueMetrics(): Promise<ValueMetricRow[]>
  getLifecycleEvents(): Promise<LifecycleEvent[]>
  getModuleUsage(): Promise<ModuleUsageRow[]>
}
