// "Point the operator-only Pricing Lab at OBrainAdapter when data exists."
// Probe getValueMetrics() — the one method guaranteed populated once §6 step 1
// (payment_processed + active_client_snapshot) has run at least once — and
// use OBrainAdapter for everything if it returns real rows. Otherwise fall
// back to MockAdapter so the Lab still renders (per spec §5's "keep
// MockAdapter as fallback" requirement) before any events have backfilled.
import { MockAdapter } from './MockAdapter'
import { OBrainAdapter } from './OBrainAdapter'
import type { DataAdapter } from './types'

export * from './types'
export { MockAdapter } from './MockAdapter'
export { OBrainAdapter } from './OBrainAdapter'

export async function resolveAdapter(): Promise<DataAdapter> {
  const real = new OBrainAdapter()
  try {
    const rows = await real.getValueMetrics()
    if (rows.length > 0) return real
  } catch {
    // Unreachable, unauthorized, or no token configured — demo mode.
  }
  return new MockAdapter()
}
