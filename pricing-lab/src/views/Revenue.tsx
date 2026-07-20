import {
  Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { REVENUE_HISTORY, TIER_COLORS } from '../data'
import { fmtUsd } from '../lib/pricing'

export default function Revenue() {
  const last = REVENUE_HISTORY[REVENUE_HISTORY.length - 1]!
  const prev = REVENUE_HISTORY[REVENUE_HISTORY.length - 2]!
  const total = (m: typeof last) => m.pro + m.business + m.enterprise + m.addons
  const mom = (total(last) / total(prev) - 1) * 100

  return (
    <section data-testid="view-revenue">
      <h2 className="view-title">Revenue</h2>
      <p className="view-sub">MRR by tier plus add-ons, Jan–Jun 2026 (demo dataset).</p>

      <div className="grid cols-3">
        <div className="card accent">
          <h3>MRR (Jun)</h3>
          <div className="big">{fmtUsd(total(last))}</div>
          <div className="sub">+{mom.toFixed(1)}% month over month</div>
        </div>
        <div className="card cyan">
          <h3>Run rate</h3>
          <div className="big">{fmtUsd(total(last) * 12)}</div>
          <div className="sub">annualized from June</div>
        </div>
        <div className="card good">
          <h3>Add-ons (Jun)</h3>
          <div className="big">{fmtUsd(last.addons)}</div>
          <div className="sub">{((last.addons / total(last)) * 100).toFixed(1)}% of MRR</div>
        </div>
      </div>

      <div className="card chart-card tall" style={{ marginTop: 14 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={REVENUE_HISTORY} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232a3b" vertical={false} />
            <XAxis dataKey="month" stroke="#8b93a7" />
            <YAxis stroke="#8b93a7" tickFormatter={(v: number) => '$' + (v / 1000).toFixed(0) + 'k'} />
            <Tooltip
              contentStyle={{ background: '#131722', border: '1px solid #232a3b' }}
              formatter={(v) => fmtUsd(Number(v))}
            />
            <Legend />
            <Area stackId="1" type="monotone" dataKey="pro" name="Pro" fill={TIER_COLORS.pro} stroke={TIER_COLORS.pro} fillOpacity={0.5} />
            <Area stackId="1" type="monotone" dataKey="business" name="Business" fill={TIER_COLORS.business} stroke={TIER_COLORS.business} fillOpacity={0.5} />
            <Area stackId="1" type="monotone" dataKey="enterprise" name="Enterprise" fill={TIER_COLORS.enterprise} stroke={TIER_COLORS.enterprise} fillOpacity={0.5} />
            <Area stackId="1" type="monotone" dataKey="addons" name="Add-ons" fill="#34d399" stroke="#34d399" fillOpacity={0.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className="footnote">
        Pro carries volume; Business carries margin; add-ons are the quiet fourth tier. The simulator view lets you
        stress-test how this stack responds to price changes.
      </p>
    </section>
  )
}
