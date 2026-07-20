import { MODULE_STATS, REVENUE_HISTORY } from '../data'
import { fmtUsd } from '../lib/pricing'

export default function WhatsWorking() {
  const last = REVENUE_HISTORY[REVENUE_HISTORY.length - 1]!
  const first = REVENUE_HISTORY[0]!
  const mrr = last.pro + last.business + last.enterprise + last.addons
  const mrr0 = first.pro + first.business + first.enterprise + first.addons
  const growth = (mrr / mrr0 - 1) * 100
  const topRetention = [...MODULE_STATS].sort((a, b) => b.retentionLift - a.retentionLift).slice(0, 5)
  const topExpansion = [...MODULE_STATS].sort((a, b) => b.expansionLift - a.expansionLift).slice(0, 5)

  return (
    <section data-testid="view-working">
      <h2 className="view-title">What&apos;s Working</h2>
      <p className="view-sub">The signals that matter, distilled from the demo cohort.</p>

      <div className="grid cols-4">
        <div className="card accent">
          <h3>MRR (Jun)</h3>
          <div className="big">{fmtUsd(mrr)}</div>
          <div className="sub">+{growth.toFixed(0)}% over 6 months</div>
        </div>
        <div className="card good">
          <h3>Add-on share</h3>
          <div className="big">{((last.addons / mrr) * 100).toFixed(1)}%</div>
          <div className="sub">of MRR from add-ons</div>
        </div>
        <div className="card cyan">
          <h3>Stickiest module</h3>
          <div className="big">{topRetention[0]!.module}</div>
          <div className="sub">+{topRetention[0]!.retentionLift}pp 6-mo retention lift</div>
        </div>
        <div className="card">
          <h3>Best upgrade driver</h3>
          <div className="big">{topExpansion[0]!.module}</div>
          <div className="sub">+{topExpansion[0]!.expansionLift}pp upgrade-rate lift</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <div className="card">
          <h3>Retention drivers (top 5)</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Module</th>
                <th>Adoption</th>
                <th>Retention lift</th>
              </tr>
            </thead>
            <tbody>
              {topRetention.map((m) => (
                <tr key={m.module}>
                  <td>{m.module}</td>
                  <td>{m.adoption}%</td>
                  <td>
                    <div className="bar" style={{ width: `${m.retentionLift * 6}px` }} /> +{m.retentionLift}pp
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Expansion drivers (top 5)</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Module</th>
                <th>Adoption</th>
                <th>Upgrade lift</th>
              </tr>
            </thead>
            <tbody>
              {topExpansion.map((m) => (
                <tr key={m.module}>
                  <td>{m.module}</td>
                  <td>{m.adoption}%</td>
                  <td>
                    <div className="bar cyan" style={{ width: `${m.expansionLift * 6}px` }} /> +{m.expansionLift}pp
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="footnote">
        Reading: automation and communication modules (Workflows, Phone, Coach) correlate with both staying and
        upgrading — the pricing story should lead with them. Demo dataset; directional only.
      </p>
    </section>
  )
}
