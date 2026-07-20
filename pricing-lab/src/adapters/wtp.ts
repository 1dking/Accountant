// WtpAdapter — a cohort research source, not tenant-facing and not part of
// the DataAdapter interface (it doesn't have getAccounts/getLifecycleEvents/
// getModuleUsage; there's no product-usage meaning for a WTP interview).
// Behind the SAME operator-only boundary as OBrainAdapter: the backend gates
// GET /api/platform-admin/wtp/responses with require_platform_admin +
// require_feature("platform_admin"), and this fetch uses the identical
// bearer token — it's the same operator running both.
export interface WtpResponse {
  respondentId: string | null
  orgId: string
  segment: string | null
  tooExpensive: number
  expensive: number
  bargain: number
  tooCheap: number
  metricPref: 'Clients' | 'GMV' | 'Other'
  gmvFairness: string | null
  react49: string | null
  react179: string | null
}

const API_BASE = import.meta.env.VITE_OBRAIN_API_BASE || '/api'
const ADMIN_TOKEN = import.meta.env.VITE_OBRAIN_ADMIN_TOKEN as string | undefined

export interface WtpAdapter {
  getWtpResponses(): Promise<WtpResponse[]>
}

export class BackendWtpAdapter implements WtpAdapter {
  async getWtpResponses(): Promise<WtpResponse[]> {
    if (!ADMIN_TOKEN) return []
    const res = await fetch(`${API_BASE}/platform-admin/wtp/responses`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
    if (!res.ok) return []
    const body = await res.json()
    return (body.data ?? []) as WtpResponse[]
  }
}

export function createWtpAdapter(): WtpAdapter {
  return new BackendWtpAdapter()
}
