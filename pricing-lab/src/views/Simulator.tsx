import { useMemo, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TIERS } from '../data'
import { defaultConfig, fmtPct, fmtUsd, project, type SimulatorConfig } from '../lib/pricing'

export default function Simulator() {
  const [cfg, setCfg] = useState<SimulatorConfig>(defaultConfig)
  const result = useMemo(() => project(cfg), [cfg])
  const baseline = useMemo(() => project(defaultConfig()), [])
  const deltaMrr = result.endingMrr - baseline.endingMrr

  const setPrice = (key: keyof SimulatorConfig['prices'], value: number) =>
    setCfg((c) => ({ ...c, prices: { ...c.prices, [key]: Math.max(0, value) } }))

  return (
    <section data-testid="view-simulator">
      <h2 className="view-title">Pricing Simulator</h2>
      <p className="view-sub">
        Change prices and assumptions; the 12-month projection recalculates live. Baseline = current real prices.
      </p>

      <div className="grid cols-4">
        <div className="card accent">
          <h3>Projected MRR (mo 12)</h3>
          <div className="big" data-testid="sim-mrr">{fmtUsd(result.endingMrr)}</div>
          <div className="sub" data-testid="sim-delta">
            {deltaMrr >= 0 ? '+' : ''}{fmtUsd(deltaMrr)} vs baseline
          </div>
        </div>
        <div className="card cyan">
          <h3>Projected ARR</h3>
          <div className="big" data-testid="sim-arr">{fmtUsd(result.arr)}</div>
          <div className="sub">ending MRR × 12</div>
        </div>
        <div className="card good">
          <h3>Net revenue retention</h3>
          <div className="big" data-testid="sim-nrr">{fmtPct(result.annualNrr)}</div>
          <div className="sub">annualized; {fmtPct(result.monthlyNrr)} monthly</div>
        </div>
        <div className="card">
          <h3>Blended ARPU</h3>
          <div className="big" data-testid="sim-arpu">{fmtUsd(result.blendedArpu)}</div>
          <div className="sub">{Math.round(result.payingCustomers)} paying accounts</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <div className="card">
          <h3>Tier prices ($/mo)</h3>
          {TIERS.filter((t) => t.price > 0).map((t) => (
            <div className="price-row" style={{ marginBottom: 10 }} key={t.key}>
              <span className="tier-name">{t.name}</span>
              <input
                type="number"
                min={0}
                step={1}
                value={cfg.prices[t.key]}
                data-testid={`price-${t.key}`}
                onChange={(e) => setPrice(t.key, Number(e.target.value))}
              />
              <span className="pill">baseline {fmtUsd(t.price)}</span>
            </div>
          ))}
          <p className="footnote">Starter stays $0 — its price is the funnel.</p>
        </div>

        <div className="card">
          <h3>Assumptions</h3>
          <div className="controls">
            <div className="control">
              <label>
                Monthly signups: <span className="val">{cfg.monthlySignups}</span>
              </label>
              <input
                type="range" min={100} max={5000} step={50} value={cfg.monthlySignups}
                data-testid="slider-signups"
                onChange={(e) => setCfg((c) => ({ ...c, monthlySignups: Number(e.target.value) }))}
              />
            </div>
            <div className="control">
              <label>
                Price elasticity: <span className="val">{cfg.elasticity.toFixed(1)}</span>
              </label>
              <input
                type="range" min={0} max={2} step={0.1} value={cfg.elasticity}
                data-testid="slider-elasticity"
                onChange={(e) => setCfg((c) => ({ ...c, elasticity: Number(e.target.value) }))}
              />
            </div>
            <div className="control">
              <label>
                Add-on attach: <span className="val">{Math.round(cfg.addonAttach * 100)}%</span>
              </label>
              <input
                type="range" min={0} max={0.6} step={0.05} value={cfg.addonAttach}
                data-testid="slider-addons"
                onChange={(e) => setCfg((c) => ({ ...c, addonAttach: Number(e.target.value) }))}
              />
            </div>
            <div className="control">
              <label>
                Monthly expansion: <span className="val">{(cfg.expansionRate * 100).toFixed(1)}%</span>
              </label>
              <input
                type="range" min={0} max={0.05} step={0.005} value={cfg.expansionRate}
                data-testid="slider-expansion"
                onChange={(e) => setCfg((c) => ({ ...c, expansionRate: Number(e.target.value) }))}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="card chart-card" style={{ marginTop: 14 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={result.series} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232a3b" vertical={false} />
            <XAxis dataKey="month" stroke="#8b93a7" tickFormatter={(m: number) => 'M' + m} />
            <YAxis stroke="#8b93a7" tickFormatter={(v: number) => '$' + (v / 1000).toFixed(0) + 'k'} />
            <Tooltip
              contentStyle={{ background: '#131722', border: '1px solid #232a3b' }}
              formatter={(v) => fmtUsd(Number(v))}
              labelFormatter={(m) => 'Month ' + m}
            />
            <Line type="monotone" dataKey="mrr" name="Projected MRR" stroke="#8b5cf6" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="footnote">
        Model: price-elastic conversion (multiplier = (base/price)^elasticity, clamped), per-tier churn
        (6/3/2/1%), expansion compounding on the existing book, add-on basket $20. NRR measures the existing
        book only — new sales excluded. Assumptions are demo-grade; the point is comparing scenarios, not
        forecasting truth.
      </p>
    </section>
  )
}
