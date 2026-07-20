// Van Westendorp Price Sensitivity Meter — replicates OBrain_WTP_Capture.xlsx
// (Van Westendorp tab) exactly: the same 26-point price grid, the same four
// cumulative-curve formulas, and the same nearest-grid-price crossover
// method for PMC/PME/OPP/IPP. This is not a from-scratch VW implementation;
// it's a line-for-line port so the Lab and the workbook never disagree.
import type { WtpResponse } from '../adapters/wtp'

// Interviews!$A$6:$A$31 in the workbook.
export const PRICE_GRID = [
  0, 10, 19, 25, 29, 39, 49, 59, 69, 79, 89, 99, 119, 149, 179, 199,
  229, 249, 279, 299, 349, 399, 449, 499, 549, 599,
] as const

export interface VwCurvePoint {
  price: number
  tooCheapPct: number
  bargainPct: number
  expensivePct: number
  tooExpensivePct: number
}

export interface VwReadouts {
  pmc: number | null // Accept. low — |TooCheap − Expensive| crossover
  pme: number | null // Accept. high — |TooExpensive − Bargain| crossover
  opp: number | null // Optimal — |TooCheap − TooExpensive| crossover
  ipp: number | null // Indifference — |Bargain − Expensive| crossover
  n: number
}

export interface VwResult {
  curve: VwCurvePoint[]
  readouts: VwReadouts
}

function nearestGridCrossover(diffs: number[]): number | null {
  if (diffs.length === 0) return null
  let bestIdx = 0
  for (let i = 1; i < diffs.length; i++) {
    if (diffs[i]! < diffs[bestIdx]!) bestIdx = i
  }
  return PRICE_GRID[bestIdx] ?? null
}

/** Mirrors Interviews!$B$3 = COUNT(Q4:Q203) — respondents with a complete VW set. */
export function computeVanWestendorp(responses: WtpResponse[]): VwResult {
  const n = responses.length
  const curve: VwCurvePoint[] = PRICE_GRID.map((price) => {
    if (n === 0) {
      return { price, tooCheapPct: 0, bargainPct: 0, expensivePct: 0, tooExpensivePct: 0 }
    }
    const tooCheapPct = responses.filter((r) => r.tooCheap >= price).length / n
    const bargainPct = responses.filter((r) => r.bargain >= price).length / n
    const expensivePct = responses.filter((r) => r.expensive <= price).length / n
    const tooExpensivePct = responses.filter((r) => r.tooExpensive <= price).length / n
    return { price, tooCheapPct, bargainPct, expensivePct, tooExpensivePct }
  })

  if (n === 0) {
    return { curve, readouts: { pmc: null, pme: null, opp: null, ipp: null, n: 0 } }
  }

  const oppDiffs = curve.map((c) => Math.abs(c.tooCheapPct - c.tooExpensivePct))
  const ippDiffs = curve.map((c) => Math.abs(c.bargainPct - c.expensivePct))
  const pmcDiffs = curve.map((c) => Math.abs(c.tooCheapPct - c.expensivePct))
  const pmeDiffs = curve.map((c) => Math.abs(c.tooExpensivePct - c.bargainPct))

  return {
    curve,
    readouts: {
      pmc: nearestGridCrossover(pmcDiffs),
      pme: nearestGridCrossover(pmeDiffs),
      opp: nearestGridCrossover(oppDiffs),
      ipp: nearestGridCrossover(ippDiffs),
      n,
    },
  }
}
