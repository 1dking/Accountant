// Fetches the four aggregate endpoints backed by app/events/router.py.
// Operator-only: the backend gates every route on require_platform_admin
// (admin role or a super-admin email) PLUS require_feature("platform_admin")
// at the router mount. This tool is an internal instrument run by whoever
// operates the deployment, not something end customers see — so auth here is
// "paste an admin token into .env.local," not a login screen.
import type { Account, DataAdapter, LifecycleEvent, ModuleUsageRow, ValueMetricRow } from './types'

const API_BASE = import.meta.env.VITE_OBRAIN_API_BASE || '/api'
const ADMIN_TOKEN = import.meta.env.VITE_OBRAIN_ADMIN_TOKEN as string | undefined

async function getJSON<T>(path: string): Promise<T> {
  if (!ADMIN_TOKEN) {
    throw new Error(
      'VITE_OBRAIN_ADMIN_TOKEN is not set — see pricing-lab/.env.example. ' +
      'OBrainAdapter requires an admin (or super-admin-email) session token.'
    )
  }
  const res = await fetch(`${API_BASE}/platform-admin/events/${path}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  })
  if (!res.ok) {
    throw new Error(`OBrainAdapter: GET ${path} -> HTTP ${res.status}`)
  }
  const body = await res.json()
  return body.data as T
}

export class OBrainAdapter implements DataAdapter {
  readonly source = 'obrain' as const

  getAccounts(): Promise<Account[]> {
    return getJSON<Account[]>('accounts')
  }

  getValueMetrics(): Promise<ValueMetricRow[]> {
    return getJSON<ValueMetricRow[]>('value-metrics')
  }

  getLifecycleEvents(): Promise<LifecycleEvent[]> {
    return getJSON<LifecycleEvent[]>('lifecycle')
  }

  getModuleUsage(): Promise<ModuleUsageRow[]> {
    return getJSON<ModuleUsageRow[]>('module-usage')
  }
}
