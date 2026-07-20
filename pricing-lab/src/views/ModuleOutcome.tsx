import {
  CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { MODULE_STATS } from '../data'

const CATEGORY_COLORS: Record<string, string> = {
  CRM: '#8b5cf6', Sales: '#a78bfa', Accounting: '#34d399', Comms: '#22d3ee',
  Meetings: '#60a5fa', Automation: '#f59e0b', Content: '#f472b6', Storage: '#94a3b8',
  Office: '#818cf8', AI: '#e879f9', Admin: '#64748b',
}

export default function ModuleOutcome() {
  return (
    <section data-testid="view-modules">
      <h2 className="view-title">Module → Outcome</h2>
      <p className="view-sub">
        Each dot is a module: adoption (x) vs retention lift (y); dot size = upgrade lift. Demo cohort.
      </p>

      <div className="card chart-card tall">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 24, bottom: 10, left: 0 }}>
            <CartesianGrid stroke="#232a3b" />
            <XAxis
              type="number" dataKey="adoption" name="Adoption %" unit="%" stroke="#8b93a7"
              domain={[0, 100]} label={{ value: 'Weekly adoption %', position: 'insideBottom', offset: -4, fill: '#8b93a7' }}
            />
            <YAxis
              type="number" dataKey="retentionLift" name="Retention lift" unit="pp" stroke="#8b93a7"
              label={{ value: 'Retention lift (pp)', angle: -90, position: 'insideLeft', fill: '#8b93a7' }}
            />
            <ZAxis type="number" dataKey="expansionLift" range={[80, 500]} name="Upgrade lift" unit="pp" />
            <Tooltip
              contentStyle={{ background: '#131722', border: '1px solid #232a3b' }}
              formatter={(value, name) => [String(value), String(name)]}
              labelFormatter={() => ''}
              cursor={{ strokeDasharray: '4 4' }}
            />
            <Scatter data={MODULE_STATS}>
              {MODULE_STATS.map((m) => (
                <Cell key={m.module} fill={CATEGORY_COLORS[m.category] ?? '#8b5cf6'} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h3>All modules</h3>
        <table className="data">
          <thead>
            <tr>
              <th>Module</th><th>Category</th><th>Adoption</th><th>Retention lift</th><th>Upgrade lift</th>
            </tr>
          </thead>
          <tbody>
            {[...MODULE_STATS]
              .sort((a, b) => b.retentionLift + b.expansionLift - (a.retentionLift + a.expansionLift))
              .map((m) => (
                <tr key={m.module}>
                  <td>{m.module}</td>
                  <td><span className="pill">{m.category}</span></td>
                  <td>{m.adoption}%</td>
                  <td>+{m.retentionLift}pp</td>
                  <td>+{m.expansionLift}pp</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <p className="footnote">
        Top-right is gold: high adoption AND high retention lift. Low-adoption/high-lift modules (Coach, Workflows)
        are the onboarding opportunities — getting more accounts into them should move churn.
      </p>
    </section>
  )
}
