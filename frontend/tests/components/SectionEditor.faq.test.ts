/**
 * SectionEditor — FAQ accordion inline-edit fix (Commit 5.1).
 *
 * Regression guard for the bug where clicking the chevron icon or
 * <summary> padding in a FAQ accordion did nothing: the iframe click
 * handler called preventDefault() on any non-TEXT_TAGS tag, which
 * blocked the browser's native <details> toggle.
 *
 * The fix walks up to find a <summary> ancestor and either:
 *   - returns early without preventDefault when the click is on the
 *     chevron / summary itself (so native toggle fires), or
 *   - preventDefault to block the toggle when the click is on inner
 *     text (so editing doesn't flap the accordion open/closed).
 *
 * Static parse of EDITOR_SCRIPT — matches the InsertionZone test
 * style (read source, assert string patterns).
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import path from 'path'

const TSX_PATH = path.resolve(
  __dirname,
  '..',
  '..',
  'src',
  'components',
  'pages',
  'SectionEditor.tsx',
)

describe('SectionEditor FAQ accordion handling (Commit 5.1)', () => {
  const src = readFileSync(TSX_PATH, 'utf8')

  // Extract the EDITOR_SCRIPT const body — the template literal that
  // gets injected into each section iframe.
  function editorScriptBody(): string {
    const m = src.match(/const EDITOR_SCRIPT = `([\s\S]*?)`/)
    return m ? m[1] : ''
  }

  it('iframe click handler walks up to find a <summary> ancestor', () => {
    const body = editorScriptBody()
    expect(body, 'EDITOR_SCRIPT must be defined').not.toBe('')
    expect(body).toMatch(/closest\s*\(\s*['"]summary['"]\s*\)/)
  })

  it('iframe click handler returns early (no preventDefault) on chevron/summary click', () => {
    const body = editorScriptBody()
    // The summary-handling branch must contain a `return;` before any
    // unconditional preventDefault — otherwise the browser's native
    // <details> toggle can't fire.
    const summaryBlock = body.match(
      /summaryAncestor\s*&&[\s\S]{0,400}?return\s*;/,
    )
    expect(
      summaryBlock,
      'summary-handling branch missing early return',
    ).toBeTruthy()
  })

  it('iframe click handler preventDefaults text clicks inside summary', () => {
    const body = editorScriptBody()
    // After the early-return branch there must be a path that calls
    // preventDefault() when we're inside a summary on a text element
    // — otherwise typing into the question text re-toggles the
    // accordion on every click.
    const textBranch = body.match(
      /if\s*\(\s*summaryAncestor\s*\)\s*\{[\s\S]{0,80}?preventDefault/,
    )
    expect(
      textBranch,
      'no preventDefault for text-inside-summary case',
    ).toBeTruthy()
  })
})
