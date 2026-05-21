/**
 * Insertion zone — regression test for Commit 3.6 bug.
 *
 * Commit 3.6 shipped insertion zones with 4px rest height + zero-opacity
 * contents (transparent line, opacity:0 button). Result: invisible to
 * users. This test asserts the at-rest visibility contract so the
 * regression can't slip back.
 *
 * Scope: parse section-editor.css and assert
 *   - .se-insertion-line has a non-transparent rest background
 *   - .se-insertion-button has non-zero rest opacity
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import path from 'path'

const CSS_PATH = path.resolve(
  __dirname,
  '..',
  '..',
  'src',
  'components',
  'pages',
  'section-editor.css',
)

describe('Insertion zone at-rest visibility', () => {
  const css = readFileSync(CSS_PATH, 'utf8')

  // Pull the first block following each selector (up to its closing }).
  function ruleBlock(selector: string): string {
    const re = new RegExp(
      `\\.${selector.replace(/[-/\\^$*+?.()|[\\]{}]/g, '\\$&')}\\s*\\{([^}]*)\\}`,
      'g',
    )
    const m = re.exec(css)
    return m ? m[1] : ''
  }

  it('.se-insertion-line at rest has non-zero background opacity', () => {
    const block = ruleBlock('se-insertion-line')
    expect(block, 'rule must exist').not.toBe('')
    // Reject the regression patterns:
    //   - transparent
    //   - rgba(_, _, _, 0)  (alpha 0)
    //   - gradient that's all alpha-0 stops
    const bgMatch = block.match(/background\s*:\s*([^;]+);/)
    expect(bgMatch, 'background must be set').toBeTruthy()
    const bg = bgMatch![1].trim()
    // Must not be plain "transparent" or alpha-0 rgba
    expect(bg).not.toBe('transparent')
    expect(bg).not.toMatch(/rgba\([^)]*,\s*0\s*\)/)
    // Specifically: must have a non-zero alpha somewhere
    const alphaMatches = [...bg.matchAll(/rgba\([^)]*,\s*([\d.]+)\s*\)/g)]
    const hasNonZeroAlpha = alphaMatches.some((m) => parseFloat(m[1]) > 0)
    expect(hasNonZeroAlpha, `at-rest background "${bg}" has no visible alpha`).toBe(true)
  })

  it('.se-insertion-button at rest has non-zero opacity', () => {
    const block = ruleBlock('se-insertion-button')
    expect(block, 'rule must exist').not.toBe('')
    const opacityMatch = block.match(/opacity\s*:\s*([\d.]+)/)
    expect(opacityMatch, 'opacity must be set').toBeTruthy()
    const opacity = parseFloat(opacityMatch![1])
    expect(opacity, 'at-rest opacity must be > 0').toBeGreaterThan(0)
  })

  it('.se-insertion-zone at rest is taller than 4px (discoverable target)', () => {
    const block = ruleBlock('se-insertion-zone')
    expect(block, 'rule must exist').not.toBe('')
    const heightMatch = block.match(/height\s*:\s*(\d+)px/)
    expect(heightMatch, 'height must be set').toBeTruthy()
    const height = parseInt(heightMatch![1], 10)
    // Commit 3.6 shipped 4px → invisible target. Anything ≥ 10 is fine.
    expect(height, 'at-rest height too thin for discovery').toBeGreaterThanOrEqual(10)
  })
})
