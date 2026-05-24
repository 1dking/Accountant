/**
 * StyleEditorDrawer — Commit 6 Workstream A.
 *
 * Right-side Liquid Glass drawer for element-level style overrides.
 * Selector + per-selector style dict are persisted to
 * sections_json[i].style_overrides via PATCH /sections/{idx}. compile_page
 * emits scoped CSS rules per selector (see backend/compiler.py).
 *
 * Control sets are picked from the selected element's tag:
 *   - TEXT (h1-h6, p, span, a, li, em, strong, td, th, label):
 *       font family, weight, size, line-height, letter-spacing,
 *       alignment, transform, color
 *   - CONTAINER (section pseudo-selector — set when the user opens
 *     the drawer without first clicking a text element):
 *       background, padding, margin, border-radius, border, shadow
 *   - BUTTON: text + container controls
 *   - IMAGE: object-fit, position, opacity, radius
 *
 * Live preview path: every change posts a `style-overrides-preview`
 * message to the section's iframe, which injects/updates a
 * <style id="se-overrides"> block in the iframe head — no full srcdoc
 * rebuild, no Tailwind/GSAP reload. Debounced PATCH then persists.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { X, RotateCcw } from 'lucide-react'
import { pagesApi } from '@/api/pages'
import './style-editor-drawer.css'

// ---------------------------------------------------------------------------
// Catalog — must stay in sync with backend/compiler.py GOOGLE_FONTS_CATALOG.
// Sorted by aesthetic family so the dropdown reads like a designer's
// shortlist, not alphabetical noise.
// ---------------------------------------------------------------------------
export const GOOGLE_FONTS: string[] = [
  // Modern neo-grotesque (default OSM palette)
  'Inter', 'Geist', 'Mona Sans', 'Manrope', 'DM Sans', 'Plus Jakarta Sans',
  'Outfit', 'Work Sans', 'Space Grotesk',
  // Classic / utility
  'Roboto', 'Open Sans', 'Lato', 'Nunito', 'Source Sans 3', 'Poppins',
  'IBM Plex Sans',
  // Editorial / display
  'Playfair Display', 'Cormorant Garamond', 'Merriweather',
  // Monospace
  'JetBrains Mono',
]

const WEIGHT_OPTIONS: { value: string; label: string }[] = [
  { value: '300', label: 'Light' },
  { value: '400', label: 'Regular' },
  { value: '500', label: 'Medium' },
  { value: '600', label: 'Semibold' },
  { value: '700', label: 'Bold' },
  { value: '800', label: 'Extra-bold' },
]

const TRANSFORM_OPTIONS: { value: string; label: string }[] = [
  { value: 'none', label: 'Aa' },
  { value: 'uppercase', label: 'AB' },
  { value: 'lowercase', label: 'ab' },
  { value: 'capitalize', label: 'Aa Bb' },
]

const SHADOW_PRESETS: { value: string; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: '0 1px 2px rgba(0,0,0,0.06)', label: 'sm' },
  { value: '0 4px 12px rgba(0,0,0,0.10)', label: 'md' },
  { value: '0 8px 24px rgba(0,0,0,0.14)', label: 'lg' },
  { value: '0 16px 40px rgba(0,0,0,0.18)', label: 'xl' },
  { value: '0 24px 64px rgba(0,0,0,0.24)', label: '2xl' },
]

// Brand swatches — keep aligned with OCIDM gradient palette in
// variant_seeds.py (indigo / violet / fuchsia / cyan / emerald / amber
// + dark base + paper white).
const BRAND_SWATCHES: string[] = [
  '#0f1320', '#ffffff', '#f8fafc',
  '#6366f1', '#8b5cf6', '#ec4899',
  '#06b6d4', '#10b981', '#f59e0b',
]

// ---------------------------------------------------------------------------
// Element type classification (mirrors EDITOR_SCRIPT TEXT_TAGS list)
// ---------------------------------------------------------------------------
type ElementCategory = 'text' | 'container' | 'image' | 'button'

export function categorizeSelector(tag: string): ElementCategory {
  const t = tag.toLowerCase()
  if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'li',
       'em', 'strong', 'td', 'th', 'label'].includes(t)) {
    return 'text'
  }
  if (t === 'button') return 'button'
  if (t === 'img') return 'image'
  return 'container'  // section, div, header, footer, default
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface Props {
  open: boolean
  pageId: string
  sectionIndex: number
  /** CSS selector being styled — e.g. "h1", "section", "p", "button". */
  selector: string
  /** Section's existing style_overrides — drawer reads to pre-fill,
   *  writes to merged. */
  initialOverrides?: Record<string, Record<string, string | number>>
  /** Called after each successful PATCH so the parent can refetch the
   *  page to pick up the recompiled html. */
  onSaved: () => void
  /** Direct live-preview channel — called on every control change with
   *  the merged overrides dict so the SectionEditor can postMessage
   *  to the iframe immediately (no PATCH round-trip). */
  onPreview: (overrides: Record<string, Record<string, string | number>>) => void
  onClose: () => void
}

export default function StyleEditorDrawer({
  open, pageId, sectionIndex, selector, initialOverrides,
  onSaved, onPreview, onClose,
}: Props) {
  const category = useMemo(() => categorizeSelector(selector), [selector])

  // Local state — merged dict the drawer mutates. Persisted dict
  // updates only after the PATCH lands; in-progress edits live here.
  const [overrides, setOverrides] = useState<
    Record<string, Record<string, string | number>>
  >(initialOverrides ?? {})

  // Reset state when drawer opens or selector changes.
  useEffect(() => {
    if (open) {
      setOverrides(initialOverrides ?? {})
    }
  }, [open, selector, initialOverrides])

  // The currently-targeted selector's style dict (creates an empty
  // one in local state on first edit; we only persist on save).
  const styles = overrides[selector] || {}

  /** Update a single CSS property for the active selector. Triggers
   *  immediate live preview + debounced PATCH. */
  const updateStyle = useCallback(
    (prop: string, value: string | number | null) => {
      setOverrides((cur) => {
        const next = { ...cur }
        const sel = { ...(next[selector] || {}) }
        if (value === null || value === '') {
          delete sel[prop]
        } else {
          sel[prop] = value
        }
        if (Object.keys(sel).length === 0) {
          delete next[selector]
        } else {
          next[selector] = sel
        }
        // Live preview — fires before PATCH so the iframe paints
        // immediately. Persistence catches up via the effect below.
        onPreview(next)
        return next
      })
    },
    [selector, onPreview],
  )

  // Debounced PATCH — fires 400ms after the user stops editing.
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const patchMut = useMutation({
    mutationFn: (next: Record<string, Record<string, string | number>>) =>
      pagesApi.patchSection(pageId, sectionIndex, {
        style_overrides: Object.keys(next).length === 0 ? null : next,
      }),
    onSuccess: () => {
      setSaveState('saved')
      onSaved()
      setTimeout(() => setSaveState('idle'), 1200)
    },
    onError: (e: any) => {
      setSaveState('idle')
      toast.error(`Style save failed: ${e?.message || 'unknown'}`)
    },
  })

  // Track the last serialization we PATCHed so the debounce effect
  // doesn't fire on the initial mount or on every render.
  const lastSavedRef = useRef<string>(JSON.stringify(initialOverrides ?? {}))
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!open) return
    const serialized = JSON.stringify(overrides)
    if (serialized === lastSavedRef.current) return
    setSaveState('saving')
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      patchMut.mutate(overrides)
      lastSavedRef.current = serialized
    }, 400)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // patchMut intentionally excluded — stable across renders
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overrides, open])

  // Reset overrides for the active selector only — leaves other
  // selectors in the section alone.
  const handleResetSelector = () => {
    setOverrides((cur) => {
      const next = { ...cur }
      delete next[selector]
      onPreview(next)
      return next
    })
  }

  if (!open) return null

  return (
    <div
      className="sed-modal sed-backdrop fixed inset-0 z-[60] flex justify-end"
      onClick={onClose}
    >
      <div
        className="sed-drawer h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold">Style</h2>
            <span className="sed-selector-chip">{selector}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/8 text-white/70 hover:text-white transition"
            aria-label="Close style editor"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {(category === 'text' || category === 'button') && (
            <TextControls styles={styles} update={updateStyle} />
          )}
          {(category === 'container' || category === 'button') && (
            <ContainerControls styles={styles} update={updateStyle} />
          )}
          {category === 'image' && (
            <ImageControls styles={styles} update={updateStyle} />
          )}
        </div>

        {/* Footer */}
        <div className="sed-footer">
          <button onClick={handleResetSelector} className="sed-reset">
            <RotateCcw className="h-3.5 w-3.5" /> Reset this element
          </button>
          <span className={`sed-status ${saveState}`}>
            {saveState === 'saving' ? 'Saving…'
              : saveState === 'saved' ? 'Saved'
              : ''}
          </span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components — one per element category
// ---------------------------------------------------------------------------

type CSSDict = Record<string, string | number>
type UpdateFn = (prop: string, value: string | number | null) => void

function TextControls({ styles, update }: { styles: CSSDict; update: UpdateFn }) {
  return (
    <>
      <div className="sed-section-header">Typography</div>

      <div className="sed-row">
        <span className="sed-label">Font</span>
        <select
          className="sed-select"
          value={String(styles.fontFamily || '')}
          onChange={(e) =>
            update('fontFamily', e.target.value || null)
          }
        >
          <option value="">Default</option>
          {GOOGLE_FONTS.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>

      <div className="sed-row">
        <span className="sed-label">Weight</span>
        <select
          className="sed-select"
          value={String(styles.fontWeight || '')}
          onChange={(e) =>
            update('fontWeight', e.target.value || null)
          }
        >
          <option value="">Default</option>
          {WEIGHT_OPTIONS.map((w) => (
            <option key={w.value} value={w.value}>{w.label}</option>
          ))}
        </select>
      </div>

      <SliderRow
        label="Size"
        min={10}
        max={128}
        step={1}
        suffix="px"
        value={parsePx(styles.fontSize, 16)}
        onChange={(n) => update('fontSize', `${n}px`)}
      />

      <SliderRow
        label="Line height"
        min={0.8}
        max={2.5}
        step={0.05}
        value={parseFloatVal(styles.lineHeight, 1.5)}
        onChange={(n) => update('lineHeight', String(n))}
      />

      <SliderRow
        label="Letter spc"
        min={-0.10}
        max={0.20}
        step={0.005}
        suffix="em"
        decimals={3}
        value={parseEm(styles.letterSpacing, 0)}
        onChange={(n) => update('letterSpacing', `${n}em`)}
      />

      <div className="sed-row">
        <span className="sed-label">Align</span>
        <div className="sed-button-group">
          {(['left', 'center', 'right', 'justify'] as const).map((a) => (
            <button
              key={a}
              className={styles.textAlign === a ? 'active' : ''}
              onClick={() => update('textAlign', styles.textAlign === a ? null : a)}
            >
              {a[0].toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="sed-row">
        <span className="sed-label">Transform</span>
        <div className="sed-button-group">
          {TRANSFORM_OPTIONS.map((o) => (
            <button
              key={o.value}
              className={styles.textTransform === o.value ? 'active' : ''}
              onClick={() =>
                update('textTransform', styles.textTransform === o.value ? null : o.value)
              }
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sed-section-header">Color</div>
      <ColorRow
        label="Text"
        value={String(styles.color || '#ffffff')}
        onChange={(v) => update('color', v || null)}
      />
    </>
  )
}

function ContainerControls({
  styles, update,
}: { styles: CSSDict; update: UpdateFn }) {
  return (
    <>
      <div className="sed-section-header">Background</div>
      <ColorRow
        label="Color"
        value={String(styles.backgroundColor || '#0f1320')}
        onChange={(v) => update('backgroundColor', v || null)}
      />

      <div className="sed-section-header">Spacing</div>
      <QuadRow
        label="Padding"
        prefix="padding"
        styles={styles}
        update={update}
      />
      <QuadRow
        label="Margin"
        prefix="margin"
        styles={styles}
        update={update}
      />

      <div className="sed-section-header">Border</div>
      <SliderRow
        label="Radius"
        min={0}
        max={48}
        step={1}
        suffix="px"
        value={parsePx(styles.borderRadius, 0)}
        onChange={(n) => update('borderRadius', n === 0 ? null : `${n}px`)}
      />
      <SliderRow
        label="Width"
        min={0}
        max={8}
        step={1}
        suffix="px"
        value={parsePx(styles.borderWidth, 0)}
        onChange={(n) => update('borderWidth', n === 0 ? null : `${n}px`)}
      />
      <ColorRow
        label="Color"
        value={String(styles.borderColor || '#ffffff')}
        onChange={(v) => update('borderColor', v || null)}
      />
      <div className="sed-row">
        <span className="sed-label">Style</span>
        <select
          className="sed-select"
          value={String(styles.borderStyle || 'solid')}
          onChange={(e) =>
            update('borderStyle', e.target.value === 'solid' ? null : e.target.value)
          }
        >
          <option value="solid">Solid</option>
          <option value="dashed">Dashed</option>
          <option value="dotted">Dotted</option>
        </select>
      </div>

      <div className="sed-section-header">Shadow</div>
      <div className="sed-row">
        <span className="sed-label">Preset</span>
        <select
          className="sed-select"
          value={String(styles.boxShadow || 'none')}
          onChange={(e) =>
            update('boxShadow', e.target.value === 'none' ? null : e.target.value)
          }
        >
          {SHADOW_PRESETS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>
    </>
  )
}

function ImageControls({ styles, update }: { styles: CSSDict; update: UpdateFn }) {
  return (
    <>
      <div className="sed-section-header">Image</div>
      <div className="sed-row">
        <span className="sed-label">Fit</span>
        <select
          className="sed-select"
          value={String(styles.objectFit || 'cover')}
          onChange={(e) =>
            update('objectFit', e.target.value === 'cover' ? null : e.target.value)
          }
        >
          <option value="cover">Cover</option>
          <option value="contain">Contain</option>
          <option value="fill">Fill</option>
          <option value="none">None</option>
          <option value="scale-down">Scale down</option>
        </select>
      </div>
      <SliderRow
        label="Radius"
        min={0}
        max={48}
        step={1}
        suffix="px"
        value={parsePx(styles.borderRadius, 0)}
        onChange={(n) => update('borderRadius', n === 0 ? null : `${n}px`)}
      />
      <SliderRow
        label="Opacity"
        min={0}
        max={1}
        step={0.05}
        value={parseFloatVal(styles.opacity, 1)}
        onChange={(n) => update('opacity', n === 1 ? null : String(n))}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Reusable controls
// ---------------------------------------------------------------------------

function SliderRow({
  label, min, max, step, value, suffix = '', decimals = 1, onChange,
}: {
  label: string
  min: number
  max: number
  step: number
  value: number
  suffix?: string
  decimals?: number
  onChange: (n: number) => void
}) {
  return (
    <div className="sed-row">
      <span className="sed-label">{label}</span>
      <input
        type="range"
        className="sed-slider"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="sed-value">
        {step >= 1 ? Math.round(value) : value.toFixed(decimals)}
        {suffix}
      </span>
    </div>
  )
}

function ColorRow({
  label, value, onChange,
}: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <>
      <div className="sed-row">
        <span className="sed-label">{label}</span>
        <span className="sed-color-wrap" style={{ background: value }}>
          <input
            type="color"
            value={normalizeHex(value) || '#ffffff'}
            onChange={(e) => onChange(e.target.value)}
            aria-label={`Pick ${label.toLowerCase()} color`}
          />
        </span>
        <input
          className="sed-color-hex"
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value.trim())}
          placeholder="#000000"
        />
      </div>
      <div className="sed-swatches">
        {BRAND_SWATCHES.map((s) => (
          <button
            key={s}
            type="button"
            className="sed-swatch"
            style={{ background: s }}
            onClick={() => onChange(s)}
            aria-label={`Apply brand swatch ${s}`}
          />
        ))}
      </div>
    </>
  )
}

function QuadRow({
  label, prefix, styles, update,
}: {
  label: string
  prefix: 'padding' | 'margin'
  styles: CSSDict
  update: UpdateFn
}) {
  const sides = ['Top', 'Right', 'Bottom', 'Left'] as const
  return (
    <div className="sed-row" style={{ alignItems: 'flex-start' }}>
      <span className="sed-label" style={{ paddingTop: '6px' }}>{label}</span>
      <div className="sed-quad-grid">
        {sides.map((side) => {
          const prop = `${prefix}${side}` as keyof CSSDict
          const cur = parsePx(styles[prop as string], 0)
          return (
            <div key={side} className="sed-quad-cell">
              <span style={{ width: 14 }}>{side[0]}</span>
              <input
                type="number"
                min={0}
                max={256}
                value={cur}
                onChange={(e) => {
                  const n = Number(e.target.value)
                  update(prop as string, n === 0 ? null : `${n}px`)
                }}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Value parsers — convert CSS strings back to numeric editor state
// ---------------------------------------------------------------------------

function parsePx(v: string | number | undefined, fallback: number): number {
  if (typeof v === 'number') return v
  if (!v) return fallback
  const m = v.match(/(-?\d+(?:\.\d+)?)/)
  return m ? parseFloat(m[1]) : fallback
}

function parseFloatVal(v: string | number | undefined, fallback: number): number {
  if (typeof v === 'number') return v
  if (!v) return fallback
  const n = parseFloat(v)
  return isNaN(n) ? fallback : n
}

function parseEm(v: string | number | undefined, fallback: number): number {
  return parseFloatVal(v, fallback)
}

function normalizeHex(v: string): string | null {
  if (!v) return null
  const m = v.trim().match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/)
  return m ? v.trim() : null
}
