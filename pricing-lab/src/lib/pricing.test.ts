import { describe, expect, it } from 'vitest'
import { conversionMultiplier, defaultConfig, project } from './pricing'

describe('conversionMultiplier', () => {
  it('is 1 at the baseline price', () => {
    expect(conversionMultiplier(29, 29, 1)).toBe(1)
  })
  it('drops when price rises and grows when price falls', () => {
    expect(conversionMultiplier(29, 58, 1)).toBeLessThan(1)
    expect(conversionMultiplier(29, 15, 1)).toBeGreaterThan(1)
  })
  it('elasticity 0 makes price irrelevant', () => {
    expect(conversionMultiplier(29, 290, 0)).toBe(1)
  })
  it('is clamped to a sane band', () => {
    expect(conversionMultiplier(29, 1, 3)).toBeLessThanOrEqual(2.5)
    expect(conversionMultiplier(29, 10000, 3)).toBeGreaterThanOrEqual(0.2)
  })
})

describe('project', () => {
  it('produces a growing MRR series under default assumptions', () => {
    const r = project(defaultConfig())
    expect(r.series).toHaveLength(12)
    expect(r.endingMrr).toBeGreaterThan(0)
    expect(r.series[11]!.mrr).toBeGreaterThan(r.series[0]!.mrr)
    expect(r.arr).toBeCloseTo(r.endingMrr * 12, 6)
  })

  it('raising a tier price changes the projection (the simulator is live)', () => {
    const base = project(defaultConfig())
    const cfg = defaultConfig()
    cfg.prices.pro = 59
    const changed = project(cfg)
    expect(changed.endingMrr).not.toBeCloseTo(base.endingMrr, 2)
  })

  it('higher expansion rate raises NRR', () => {
    const low = defaultConfig()
    low.expansionRate = 0
    const high = defaultConfig()
    high.expansionRate = 0.03
    expect(project(high).monthlyNrr).toBeGreaterThan(project(low).monthlyNrr)
  })

  it('NRR excludes new sales: with zero expansion it sits below 1', () => {
    const cfg = defaultConfig()
    cfg.expansionRate = 0
    const r = project(cfg)
    expect(r.monthlyNrr).toBeLessThan(1)
    expect(r.monthlyNrr).toBeGreaterThan(0.9)
  })
})
