import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { FUNNEL, TIER_COLORS } from '../data'

export default function TierFunnel() {
  const paying = FUNNEL.find((s) => s.stage === 'Paying')!
  const signups = FUNNEL.find((s) => s.stage === 'Signups')!
  const conv = (k: 'pro' | 'business' | 'enterprise') => ((paying[k] / signups[k]) * 100).toFixed(1)

  return (
    <section data-testid="view-funnel">
      <h2 className="view-title">Tier Funnel</h2>
      <p className="view-sub">Visitors → signups → activated → paying → expanded, per tier (demo cohort).</p>

      <div className="card chart-card tall">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={FUNNEL} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232a3b" vertical={false} />
            <XAxis dataKey="stage" stroke="#8b93a7" />
            <YAxis stroke="#8b93a7" scale="sqrt" />
            <Tooltip contentStyle={{ background: '#131722', border: '1px solid #232a3b' }} />
            <Legend />
            <Bar dataKey="starter" name="Starter" fill={TIER_COLORS.starter} />
            <Bar dataKey="pro" name="Pro" fill={TIER_COLORS.pro} />
            <Bar dataKey="business" name="Business" fill={TIER_COLORS.business} />
            <Bar dataKey="enterprise" name="Enterprise" fill={TIER_COLORS.enterprise} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid cols-3" style={{ marginTop: 14 }}>
        <div className="card">
          <h3>Pro signup → paid</h3>
          <div className="big">{conv('pro')}%</div>
          <div className="sub">the volume tier</div>
        </div>
        <div className="card cyan">
          <h3>Business signup → paid</h3>
          <div className="big">{conv('business')}%</div>
          <div className="sub">best mix of volume and intent</div>
        </div>
        <div className="card accent">
          <h3>Enterprise signup → paid</h3>
          <div className="big">{conv('enterprise')}%</div>
          <div className="sub">high intent, sales-assisted</div>
        </div>
      </div>

      <p className="footnote">
        The free Starter column collapses to zero at &quot;Paying&quot; by design — its job is volume at the top and
        conversion pressure into Pro. Y-axis is square-root scaled so the paid stages stay readable next to visitor volume.
      </p>
    </section>
  )
}
