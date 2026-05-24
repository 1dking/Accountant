/**
 * StyleEditorDrawer + SectionEditor — Commit 6 Workstream A + D.
 *
 *  - compileStyleOverridesPreview: mirrors backend
 *    _compile_section_styles. The drawer's live-preview channel
 *    posts the output of this function into the iframe; the iframe
 *    pastes it into <style id="se-overrides">. Must stay in sync
 *    with the backend or the editor preview drifts from the
 *    published page.
 *  - categorizeSelector: maps a clicked-element tag to one of the
 *    four drawer control sets (text / container / image / button).
 *  - SectionEditor source: hover bar contains the .se-control-divider
 *    so the primary/secondary grouping renders (Workstream D).
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import path from 'path'
import {
  compileStyleOverridesPreview,
} from '@/components/pages/SectionEditor'
import { categorizeSelector } from '@/components/pages/StyleEditorDrawer'

const SECTION_EDITOR_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'components', 'pages', 'SectionEditor.tsx'),
  'utf8',
)
const SECTION_EDITOR_CSS = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'components', 'pages', 'section-editor.css'),
  'utf8',
)

describe('compileStyleOverridesPreview (Commit 6)', () => {
  it('emits scoped CSS for a single text selector', () => {
    const css = compileStyleOverridesPreview({
      h1: { fontFamily: 'Playfair Display', fontSize: '64px', lineHeight: 0.9 },
    })
    expect(css).toContain('h1 {')
    expect(css).toContain('font-family: "Playfair Display";')
    expect(css).toContain('font-size: 64px;')
    expect(css).toContain('line-height: 0.9;')
  })

  it('camelCase → kebab-case for CSS property names', () => {
    const css = compileStyleOverridesPreview({
      section: { paddingTop: '96px', borderTopLeftRadius: '24px' },
    })
    expect(css).toContain('padding-top: 96px;')
    expect(css).toContain('border-top-left-radius: 24px;')
  })

  it('section pseudo-selector targets body > * inside the iframe scope', () => {
    // In compile_page the section selector maps to #section-{sid}.
    // In the iframe preview, the scope is already isolated so we
    // target body > * (the variant's outer element).
    const css = compileStyleOverridesPreview({
      section: { backgroundColor: '#0f1320' },
    })
    expect(css).toContain('body > * {')
    expect(css).toContain('background-color: #0f1320;')
  })

  it('rejects values containing CSS rule-block-breaking characters', () => {
    const css = compileStyleOverridesPreview({
      h1: {
        color: 'red; } body { background: hotpink',
        fontSize: '32px',
      },
    })
    expect(css).not.toContain('hotpink')
    // Safe declaration alongside the rejected one still emits
    expect(css).toContain('font-size: 32px;')
  })

  it('returns empty string for empty/null overrides', () => {
    expect(compileStyleOverridesPreview(null)).toBe('')
    expect(compileStyleOverridesPreview(undefined)).toBe('')
    expect(compileStyleOverridesPreview({})).toBe('')
    expect(compileStyleOverridesPreview({ h1: {} })).toBe('')
  })

  it('quotes multi-word font-family values', () => {
    const css = compileStyleOverridesPreview({
      h1: { fontFamily: 'Playfair Display' },
      p:  { fontFamily: 'Inter' },
    })
    expect(css).toContain('font-family: "Playfair Display";')
    // Single-word families pass through unquoted (CSS allows both).
    expect(css).toContain('font-family: Inter;')
  })
})

describe('categorizeSelector (Commit 6)', () => {
  it('routes heading and text tags to "text"', () => {
    expect(categorizeSelector('h1')).toBe('text')
    expect(categorizeSelector('H2')).toBe('text')  // case-insensitive
    expect(categorizeSelector('p')).toBe('text')
    expect(categorizeSelector('span')).toBe('text')
    expect(categorizeSelector('a')).toBe('text')
    expect(categorizeSelector('li')).toBe('text')
  })

  it('routes button → "button" (text + container controls)', () => {
    expect(categorizeSelector('button')).toBe('button')
  })

  it('routes img → "image"', () => {
    expect(categorizeSelector('img')).toBe('image')
  })

  it('routes structural / unknown tags → "container"', () => {
    expect(categorizeSelector('section')).toBe('container')
    expect(categorizeSelector('div')).toBe('container')
    expect(categorizeSelector('header')).toBe('container')
    expect(categorizeSelector('footer')).toBe('container')
    expect(categorizeSelector('unknown-tag')).toBe('container')
  })
})

describe('SectionEditor hover bar grouping (Workstream D)', () => {
  it('renders the 1px divider between primary and secondary clusters', () => {
    // Source must include the divider element and the CSS rule
    expect(SECTION_EDITOR_SRC).toMatch(/className="se-control-divider"/)
    expect(SECTION_EDITOR_CSS).toMatch(/\.se-control-divider\s*\{/)
  })

  it('hover bar order: style, animations, variant come BEFORE divider', () => {
    const styleIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Style"')
    const animIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Animations"')
    const variantIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Change variant"')
    const dividerIdx = SECTION_EDITOR_SRC.indexOf('se-control-divider')
    expect(styleIdx).toBeGreaterThan(0)
    expect(animIdx).toBeGreaterThan(styleIdx)
    expect(variantIdx).toBeGreaterThan(animIdx)
    expect(dividerIdx).toBeGreaterThan(variantIdx)
  })

  it('hover bar order: refine, duplicate, revert, delete come AFTER divider', () => {
    const dividerIdx = SECTION_EDITOR_SRC.indexOf('se-control-divider')
    const refineIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Refine with AI"')
    const duplicateIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Duplicate section"')
    const deleteIdx = SECTION_EDITOR_SRC.indexOf('aria-label="Delete section"')
    expect(refineIdx).toBeGreaterThan(dividerIdx)
    expect(duplicateIdx).toBeGreaterThan(refineIdx)
    expect(deleteIdx).toBeGreaterThan(duplicateIdx)
  })
})

describe('SectionEditor iframe live-preview script (Workstream A)', () => {
  it('EDITOR_SCRIPT broadcasts selected-element selector to the parent', () => {
    expect(SECTION_EDITOR_SRC).toMatch(/type:\s*['"]section-element-selected['"]/)
  })

  it('EDITOR_SCRIPT injects/updates <style id="se-overrides"> on preview msg', () => {
    expect(SECTION_EDITOR_SRC).toMatch(/style-overrides-preview/)
    expect(SECTION_EDITOR_SRC).toMatch(/getElementById\(['"]se-overrides['"]\)/)
  })
})
