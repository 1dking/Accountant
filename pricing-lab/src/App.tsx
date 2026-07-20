import { useEffect, useState } from 'react'
import WhatsWorking from './views/WhatsWorking'
import TierFunnel from './views/TierFunnel'
import ModuleOutcome from './views/ModuleOutcome'
import ValueMetric from './views/ValueMetric'
import Revenue from './views/Revenue'
import Simulator from './views/Simulator'
import { resolveAdapter, type AdapterSource, type ValueMetricRow } from './adapters'

const VIEW_DEFS = [
  { key: 'working', label: "What's Working" },
  { key: 'funnel', label: 'Tier Funnel' },
  { key: 'modules', label: 'Module → Outcome' },
  { key: 'value', label: 'Value-Metric Explorer' },
  { key: 'revenue', label: 'Revenue' },
  { key: 'simulator', label: 'Pricing Simulator' },
] as const

type ViewKey = (typeof VIEW_DEFS)[number]['key']

// Only the Value-Metric Explorer is adapter-driven right now — it's the one
// view OBRAIN_EVENT_SPEC.md §6 step 1 (payment_processed +
// active_client_snapshot) actually unlocks. The other five need lifecycle /
// module-usage events (steps 2-3, not emitted this pass) to be anything but
// synthetic, so they stay on the demo cohort in ../data.ts unchanged.
export default function App() {
  const [view, setView] = useState<ViewKey>('working')
  const [source, setSource] = useState<AdapterSource | 'loading'>('loading')
  const [valueMetrics, setValueMetrics] = useState<ValueMetricRow[]>([])

  useEffect(() => {
    let cancelled = false
    resolveAdapter().then(async (adapter) => {
      const rows = await adapter.getValueMetrics().catch(() => [])
      if (cancelled) return
      setSource(adapter.source)
      setValueMetrics(rows)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const views: Record<ViewKey, React.ReactNode> = {
    working: <WhatsWorking />,
    funnel: <TierFunnel />,
    modules: <ModuleOutcome />,
    value: <ValueMetric liveRows={source === 'obrain' ? valueMetrics : null} loading={source === 'loading'} />,
    revenue: <Revenue />,
    simulator: <Simulator />,
  }

  return (
    <>
      <header className="topbar">
        <h1>
          O-Brain <span>Pricing Lab</span>
        </h1>
        <nav className="nav" aria-label="Views">
          {VIEW_DEFS.map((v) => (
            <button
              key={v.key}
              className={view === v.key ? 'on' : ''}
              data-view={v.key}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </nav>
        <span className="demo-chip" data-source={source}>
          {source === 'loading' && 'Connecting…'}
          {source === 'obrain' && 'Live data — Value-Metric Explorer only; other views still demo'}
          {source === 'mock' && 'Demo dataset — synthetic cohort, real price points'}
        </span>
      </header>
      <main className="main">{views[view]}</main>
    </>
  )
}
