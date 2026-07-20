import { useEffect, useState } from 'react'
import {
  CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import { MockAdapter, type ValueMetricRow } from '../adapters'
import { TIER_COLORS } from '../data'

// Business-outcome metrics first: a value metric should track the value the
// customer receives, and "clients served" / "money processed" are the
// closest proxies this product has — and, on live data, the ONLY ones that
// exist today (OBRAIN_EVENT_SPEC.md §6 step 1).
const METRIC_DEFS = [
  { key: 'activeClients', label: 'Active clients', usd: false },
  { key: 'paymentsProcessedUSD', label: 'Payments processed (GMV)', usd: true },
  { key: 'publishedPages', label: 'Pages published', usd: false },
  { key: 'aiMessages', label: 'AI messages / mo', usd: false },
  { key: 'storageGB', label: 'Storage (GB)', usd: false },
  { key: 'seatsUsed', label: 'Seats', usd: false },
] as const

type MetricKey = (typeof METRIC_DEFS)[number]['key']

function pearsonPairs(
  rows: ValueMetricRow[],
  xFn: (r: ValueMetricRow) => number | null | undefined,
  yFn: (r: ValueMetricRow) => number | null | undefined
): number {
  const xs: number[] = []
  const ys: number[] = []
  for (const r of rows) {
    const x = xFn(r)
    const y = yFn(r)
    if (x == null || y == null) continue
    xs.push(x)
    ys.push(y)
  }
  if (xs.length < 3) return 0
  const n = xs.length
  const mx = xs.reduce((s, v) => s + v, 0) / n
  const my = ys.reduce((s, v) => s + v, 0) / n
  let num = 0, dx = 0, dy = 0
  for (let i = 0; i < n; i++) {
    const a = xs[i]! - mx
    const b = ys[i]! - my
    num += a * b
    dx += a * a
    dy += b * b
  }
  const den = Math.sqrt(dx * dy)
  return den > 0 ? num / den : 0
}

/**
 * PRIMARY score — "value-metric fit": correlation with value delivered.
 * Live data has only two outcome proxies right now (activeClients, GMV) —
 * retention/expansion need lifecycle events that don't exist until spec §6
 * step 2 ships. Demo data keeps the richer three-outcome scoring so the
 * method demo stays intact. Never silently mixes the two.
 */
function valueFit(rows: ValueMetricRow[], metric: MetricKey, isLive: boolean): number {
  const xFn = (r: ValueMetricRow) => (r[metric] as number | null | undefined) ?? null
  type OutcomeFn = (r: ValueMetricRow) => number | null
  const outcomes: OutcomeFn[] = isLive
    ? ([
        ['activeClients', (r: ValueMetricRow) => r.activeClients],
        ['paymentsProcessedUSD', (r: ValueMetricRow) => r.paymentsProcessedUSD],
      ] as Array<[string, OutcomeFn]>).filter(([k]) => k !== metric).map(([, fn]) => fn)
    : ([
        ['demoRetained6mo', (r: ValueMetricRow) => (r.demoRetained6mo ? 1 : 0)],
        ['demoExpansionMrr', (r: ValueMetricRow) => r.demoExpansionMrr ?? null],
        ['paymentsProcessedUSD', (r: ValueMetricRow) => r.paymentsProcessedUSD],
      ] as Array<[string, OutcomeFn]>).filter(([k]) => k !== metric).map(([, fn]) => fn)
  if (outcomes.length === 0) return 0
  const rs = outcomes.map((fn) => Math.abs(pearsonPairs(rows, xFn, fn)))
  return rs.reduce((s, v) => s + v, 0) / rs.length
}

/** Secondary diagnostic — demo-only (needs Account.tier, not fetched on live
 * data this pass; see honesty note in props doc below). */
function separationScore(rows: ValueMetricRow[], metric: MetricKey): number {
  const byTier = new Map<string, number[]>()
  for (const r of rows) {
    const v = r[metric] as number | null
    if (v == null || !r.demoTier) continue
    if (!byTier.has(r.demoTier)) byTier.set(r.demoTier, [])
    byTier.get(r.demoTier)!.push(v)
  }
  const groups = [...byTier.values()]
  if (groups.length < 2) return 0
  const means = groups.map((g) => g.reduce((s, v) => s + v, 0) / g.length)
  const grand = means.reduce((s, v) => s + v, 0) / means.length
  const between = means.reduce((s, m) => s + (m - grand) ** 2, 0) / means.length
  const within =
    groups.reduce((s, g, i) => s + g.reduce((ss, v) => ss + (v - means[i]!) ** 2, 0), 0) /
    Math.max(1, groups.reduce((s, g) => s + g.length, 0))
  return within > 0 ? between / within : 0
}

const fmtCompact = (v: number, usd: boolean): string => {
  const abs = Math.abs(v)
  const num = abs >= 1_000_000 ? (v / 1_000_000).toFixed(1) + 'M' : abs >= 1000 ? (v / 1000).toFixed(0) + 'k' : String(Math.round(v))
  return usd ? '$' + num : num
}

interface Props {
  /** Real ValueMetricRow[] from OBrainAdapter, or null to use the demo
   * cohort (MockAdapter). Set by App.tsx based on which adapter resolved. */
  liveRows: ValueMetricRow[] | null
  loading: boolean
}

export default function ValueMetric({ liveRows, loading }: Props) {
  const [demoRows, setDemoRows] = useState<ValueMetricRow[] | null>(null)

  useEffect(() => {
    if (liveRows === null) {
      new MockAdapter().getValueMetrics().then(setDemoRows)
    }
  }, [liveRows])

  const isLive = liveRows !== null
  const rows = isLive ? liveRows : demoRows

  if (loading || rows === null) {
    return (
      <section data-testid="view-value">
        <h2 className="view-title">Value-Metric Explorer</h2>
        <p className="view-sub">Loading…</p>
      </section>
    )
  }

  return <ValueMetricLoaded rows={rows} isLive={isLive} />
}

function ValueMetricLoaded({ rows, isLive }: { rows: ValueMetricRow[]; isLive: boolean }) {
  const available = METRIC_DEFS.filter((m) => rows.some((r) => r[m.key] != null))
  const [metric, setMetric] = useState<MetricKey>(available[0]?.key ?? 'activeClients')
  useEffect(() => {
    if (!available.some((m) => m.key === metric) && available[0]) setMetric(available[0].key)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLive])

  const active = available.find((m) => m.key === metric) ?? available[0]
  // Anchor axis: GMV, the one signal that exists in both modes — except when
  // GMV itself is the selected candidate, then fall back to active clients.
  const anchorKey: 'paymentsProcessedUSD' | 'activeClients' =
    metric === 'paymentsProcessedUSD' ? 'activeClients' : 'paymentsProcessedUSD'
  const anchorLabel = anchorKey === 'paymentsProcessedUSD' ? 'GMV ($)' : 'Active clients'

  const fits = available
    .map((m) => ({ ...m, fit: valueFit(rows, m.key, isLive), separation: separationScore(rows, m.key) }))
    .sort((a, b) => b.fit - a.fit)

  if (available.length === 0 || !active) {
    return (
      <section data-testid="view-value">
        <h2 className="view-title">Value-Metric Explorer</h2>
        <p className="view-sub">
          No value-metric candidates have data yet for this account. Once payment_processed and
          active_client_snapshot events land (OBRAIN_EVENT_SPEC.md §6 step 1), they will appear here.
        </p>
      </section>
    )
  }

  return (
    <section data-testid="view-value">
      <h2 className="view-title">Value-Metric Explorer</h2>
      <p className="view-sub">
        Candidate value metrics scored by correlation with value delivered. Each dot is {isLive ? 'a real org-month' : 'a demo account'}.
      </p>

      <div className="nav" style={{ marginBottom: 14 }}>
        {available.map((m) => (
          <button key={m.key} className={metric === m.key ? 'on' : ''} data-metric={m.key} onClick={() => setMetric(m.key)}>
            {m.label}
          </button>
        ))}
      </div>

      <div className="card chart-card tall">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 24, bottom: 10, left: 8 }}>
            <CartesianGrid stroke="#232a3b" />
            <XAxis
              type="number"
              dataKey={metric}
              name={active.label}
              stroke="#8b93a7"
              tickFormatter={(v: number) => fmtCompact(v, active.usd)}
              label={{ value: active.label, position: 'insideBottom', offset: -4, fill: '#8b93a7' }}
            />
            <YAxis
              type="number"
              dataKey={anchorKey}
              name={anchorLabel}
              stroke="#8b93a7"
              tickFormatter={(v: number) => fmtCompact(v, anchorKey === 'paymentsProcessedUSD')}
              label={{ value: anchorLabel, angle: -90, position: 'insideLeft', fill: '#8b93a7' }}
            />
            <Tooltip contentStyle={{ background: '#131722', border: '1px solid #232a3b' }} cursor={{ strokeDasharray: '4 4' }} />
            <Scatter data={rows}>
              {rows.map((r, i) => (
                <Cell
                  key={r.orgId + i}
                  fill={r.demoTier ? TIER_COLORS[r.demoTier as keyof typeof TIER_COLORS] ?? '#8b5cf6' : '#8b5cf6'}
                  fillOpacity={0.75}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="grid cols-3" style={{ marginTop: 14 }}>
        {fits.map((s, i) => (
          <div className={`card${i === 0 ? ' accent' : ''}`} key={s.key}>
            <h3>{s.label}</h3>
            <div className="big">{s.fit.toFixed(2)}</div>
            <div className="sub">
              value-metric fit (avg |r| vs {isLive ? 'GMV/active-clients' : 'outcomes'})
              {i === 0 ? ' — top in this run' : ''}
            </div>
          </div>
        ))}
      </div>

      {!isLive && (
        <div className="card" style={{ marginTop: 14 }}>
          <h3>Secondary diagnostic — tier separation (treat with suspicion)</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value-metric fit (primary)</th>
                <th>Tier separation (diagnostic)</th>
              </tr>
            </thead>
            <tbody>
              {fits.map((s) => (
                <tr key={s.key}>
                  <td>{s.label}</td>
                  <td>{s.fit.toFixed(2)}</td>
                  <td>{s.separation.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="footnote">
            Separation measures how cleanly a metric sorts accounts into the tiers they already pay for — which
            rewards whatever the current pricing is already based on. It is kept here only as a sanity check, not
            as a selection criterion.
          </p>
        </div>
      )}

      <p className="footnote">
        {isLive ? (
          <>
            <strong>Live data</strong> — {rows.length} real org-month row{rows.length === 1 ? '' : 's'} from the
            event log. Outcomes are limited to GMV and active-client count today; retention- and
            expansion-weighted fit (the fuller demo scoring) needs lifecycle events (OBRAIN_EVENT_SPEC.md §6 step
            2), not emitted yet. Tier separation isn&apos;t shown because per-org tier assignment also needs
            those events. What this proves: the method works and real payment/active-client data now flows into
            it — not which metric wins long-term.
          </>
        ) : (
          <>
            What this view is: a demonstration of the METHOD for choosing a value metric — score candidates by
            how well they track value delivered, not by how well they mirror today&apos;s tiers. What it is not:
            a finding. The cohort is synthetic, so no metric &quot;wins&quot; here in any real sense; the actual
            metric decision waits on real usage data wired in from the platform, plus willingness-to-pay
            interviews.
          </>
        )}
      </p>
    </section>
  )
}
