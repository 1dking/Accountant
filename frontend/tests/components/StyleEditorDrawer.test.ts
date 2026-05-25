/**
 * StyleEditorDrawer + SectionEditor — Commit 6 Workstream A + D,
 * plus Commit 6.0.1 fixes (scoped #id preview + non-blurring backdrop).
 *
 *  - compileStyleOverridesPreview: mirrors backend
 *    _compile_section_styles. The drawer's live-preview channel
 *    posts the output of this function into the iframe; the iframe
 *    pastes it into <style id="se-overrides">. Must stay in sync
 *    with the backend or the editor preview drifts from the
 *    published page. Commit 6.0.1: takes a sectionId arg and emits
 *    "#section-{sid} {tag}" rules so id-selector specificity beats
 *    Tailwind utility classes — same shape compile_page emits.
 *  - categorizeSelector: maps a clicked-element tag to one of the
 *    four drawer control sets (text / container / image / button).
 *  - SectionEditor source: hover bar contains the .se-control-divider
 *    so the primary/secondary grouping renders (Workstream D), and
 *    the iframe EDITOR_SCRIPT pins body id so the preview scope
 *    resolves.
 *  - .sed-backdrop: live-editing drawers DO NOT blur or dim the
 *    canvas (Commit 6.0.1 convention) — users need a sharp preview
 *    while customizing.
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
const SED_DRAWER_CSS = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'components', 'pages', 'style-editor-drawer.css'),
  'utf8',
)

const SID = 'abc123'

describe('compileStyleOverridesPreview (Commit 6 + 6.0.1)', () => {
  it('emits scoped CSS prefixed with #section-{sid}', () => {
    const css = compileStyleOverridesPreview({
      h1: { fontFamily: 'Playfair Display', fontSize: '64px', lineHeight: 0.9 },
    }, SID)
    // Commit 6.0.1 — id-prefixed so it beats Tailwind utility classes.
    expect(css).toContain(`#section-${SID} h1 {`)
    expect(css).toContain('font-family: "Playfair Display";')
    expect(css).toContain('font-size: 64px;')
    expect(css).toContain('line-height: 0.9;')
    // Must NOT emit bare-tag selector (loses specificity battle).
    expect(css).not.toMatch(/^h1 \{/m)
  })

  it('camelCase → kebab-case for CSS property names', () => {
    const css = compileStyleOverridesPreview({
      section: { paddingTop: '96px', borderTopLeftRadius: '24px' },
    }, SID)
    expect(css).toContain('padding-top: 96px;')
    expect(css).toContain('border-top-left-radius: 24px;')
  })

  it('section pseudo-selector targets wrapper + inner section', () => {
    // Mirrors backend _compile_section_styles exactly:
    //   "section" → "#section-{sid}, #section-{sid} > section"
    const css = compileStyleOverridesPreview({
      section: { backgroundColor: '#0f1320' },
    }, SID)
    expect(css).toContain(`#section-${SID}, #section-${SID} > section {`)
    expect(css).toContain('background-color: #0f1320;')
  })

  it('rejects values containing CSS rule-block-breaking characters', () => {
    const css = compileStyleOverridesPreview({
      h1: {
        color: 'red; } body { background: hotpink',
        fontSize: '32px',
      },
    }, SID)
    expect(css).not.toContain('hotpink')
    // Safe declaration alongside the rejected one still emits
    expect(css).toContain('font-size: 32px;')
  })

  it('returns empty string for empty/null overrides', () => {
    expect(compileStyleOverridesPreview(null, SID)).toBe('')
    expect(compileStyleOverridesPreview(undefined, SID)).toBe('')
    expect(compileStyleOverridesPreview({}, SID)).toBe('')
    expect(compileStyleOverridesPreview({ h1: {} }, SID)).toBe('')
  })

  it('quotes multi-word font-family values', () => {
    const css = compileStyleOverridesPreview({
      h1: { fontFamily: 'Playfair Display' },
      p:  { fontFamily: 'Inter' },
    }, SID)
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

  // Commit 6.0.1 — iframe body MUST receive id="section-{sid}" so the
  // scoped preview rules resolve and beat Tailwind utility classes on
  // specificity. Without this, every override silently no-ops in the
  // editor preview.
  it('EDITOR_SCRIPT pins body id to section-{sectionId} for #id scoping', () => {
    expect(SECTION_EDITOR_SRC).toMatch(
      /document\.body\.id\s*=\s*['"]section-['"]\s*\+\s*window\.__sectionId/,
    )
  })
})

describe('.sed-backdrop convention (Commit 6.0.1)', () => {
  // Live-editing drawers (Style, future Structure, etc.) must keep
  // the canvas SHARP and UNDIMMED. The user is editing in real time
  // and needs to see their changes clearly. Modal pattern (with blur)
  // is only correct for picker UIs where the user chooses then closes
  // — see AnimationPickerModal's .ap-backdrop.
  function backdropBlock(): string {
    const m = SED_DRAWER_CSS.match(/\.sed-backdrop\s*\{([^}]*)\}/)
    return m ? m[1] : ''
  }

  it('.sed-backdrop has NO backdrop-filter blur', () => {
    const block = backdropBlock()
    expect(block, '.sed-backdrop rule must exist').not.toBe('')
    expect(block).not.toMatch(/backdrop-filter\s*:\s*blur/)
  })

  it('.sed-backdrop has NO dimming background fill', () => {
    const block = backdropBlock()
    // Must be transparent — no rgba dim, no opaque color.
    const bg = block.match(/background\s*:\s*([^;]+);/)
    expect(bg, 'background must be declared (transparent)').toBeTruthy()
    expect(bg![1].trim()).toMatch(/^transparent$/i)
  })
})
