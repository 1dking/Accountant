/**
 * AnimationPickerModal — Commit 4B picker for the section animation
 * preset + config. Right-side Liquid Glass drawer with two
 * collapsible tiers (Entry / Scroll-driven). 14 preset cards each
 * with an inline CSS keyframe preview (no GSAP in the picker — keeps
 * the editor light). Selecting a preset opens a config panel below
 * with duration / delay / ease / stagger sliders.
 *
 * Tier 4 hover effects (hover_lift/tilt/magnetic/underline_draw) ship
 * in Commit 4B.2.
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { X, Check, ChevronDown, ChevronUp, RotateCcw, RotateCw } from 'lucide-react'
import { pagesApi } from '@/api/pages'
import './animation-picker.css'

interface PresetRow {
  id: string
  tier: 'entry' | 'scrub'
  display_name: string
  description: string
  defaults: Record<string, unknown>
}

interface PresetsResponse { data: PresetRow[] }

interface CurrentAnim {
  preset?: string
  config?: Record<string, unknown>
}

interface Props {
  open: boolean
  pageId: string
  sectionIndex: number
  /** Current section.animations (4B preset shape). Picker selects
   *  this preset on open so the user sees what's already applied. */
  current?: CurrentAnim | null
  onClose: () => void
  /** Called after the PATCH resolves successfully. Parent refetches
   *  the page to pick up the new compiled html_content. */
  onApplied: () => void
  /** Called when the user clicks the Replay button. Parent posts a
   *  replay message to the section's iframe so the animation plays
   *  again without re-PATCHing. Optional — picker still works
   *  without it. */
  onReplay?: () => void
}

const EASE_OPTIONS = [
  { value: 'power2.out', label: 'Smooth out (default)' },
  { value: 'power2.in', label: 'Smooth in' },
  { value: 'power2.inOut', label: 'Smooth in-out' },
  { value: 'power3.out', label: 'Snappy out' },
  { value: 'elastic.out(1, 0.5)', label: 'Elastic bounce' },
  { value: 'back.out(1.7)', label: 'Overshoot' },
  { value: 'none', label: 'Linear (no easing)' },
]

export default function AnimationPickerModal({
  open, pageId, sectionIndex, current, onClose, onApplied, onReplay,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(current?.preset ?? null)
  const [config, setConfig] = useState<Record<string, unknown>>(current?.config ?? {})
  const [entryOpen, setEntryOpen] = useState(true)
  const [scrubOpen, setScrubOpen] = useState(false)

  // Reset state when modal opens / target section changes
  useEffect(() => {
    if (open) {
      setSelectedId(current?.preset ?? null)
      setConfig(current?.config ?? {})
      // Auto-expand the tier the current preset belongs to
      if (current?.preset && current.preset !== 'default' && current.preset !== 'none') {
        // We don't know the tier here without the registry; will sync
        // after presets load (below).
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sectionIndex])

  const presetsQuery = useQuery<PresetsResponse>({
    queryKey: ['animation-presets'],
    queryFn: () => pagesApi.listAnimationPresets() as Promise<PresetsResponse>,
    enabled: open,
    staleTime: 5 * 60_000,
  })
  const presets = presetsQuery.data?.data ?? []
  const entryPresets = useMemo(() => presets.filter(p => p.tier === 'entry'), [presets])
  const scrubPresets = useMemo(() => presets.filter(p => p.tier === 'scrub'), [presets])

  // Once presets load, auto-expand the tier matching the current preset
  useEffect(() => {
    if (!selectedId || !presets.length) return
    const p = presets.find(x => x.id === selectedId)
    if (p?.tier === 'scrub') setScrubOpen(true)
    if (p?.tier === 'entry') setEntryOpen(true)
  }, [presets, selectedId])

  const applyMut = useMutation({
    mutationFn: (data: { preset: string; config?: Record<string, unknown> }) =>
      pagesApi.setSectionAnimation(pageId, sectionIndex, data),
    onSuccess: (_d, vars) => {
      const p = presets.find(x => x.id === vars.preset)
      toast.success(`Animation: ${p?.display_name || vars.preset}`)
      onApplied()
      onClose()
    },
    onError: (e: any) => toast.error(`Apply failed: ${e?.message || 'unknown'}`),
  })

  const handleSelect = (preset: PresetRow) => {
    setSelectedId(preset.id)
    setConfig({ ...preset.defaults })
    applyMut.mutate({ preset: preset.id, config: { ...preset.defaults } })
  }

  const handleReset = () => {
    setSelectedId(null)
    setConfig({})
    applyMut.mutate({ preset: 'default' })
  }

  const handleNone = () => {
    setSelectedId('none')
    setConfig({})
    applyMut.mutate({ preset: 'none' })
  }

  // Debounced live config updates — re-apply preset with new config
  // after user finishes adjusting a slider. Same PATCH endpoint;
  // backend merges with defaults.
  useEffect(() => {
    if (!selectedId || selectedId === 'default' || selectedId === 'none') return
    if (!open) return
    const t = setTimeout(() => {
      applyMut.mutate({ preset: selectedId, config })
    }, 350)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(config), selectedId])

  if (!open) return null

  const selectedPreset = selectedId
    ? presets.find(p => p.id === selectedId)
    : null

  return (
    <div
      className="ap-modal ap-backdrop fixed inset-0 z-[55] flex justify-end"
      onClick={onClose}
    >
      <div
        className="ap-drawer w-full max-w-md h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <h2 className="text-base font-semibold">Animation</h2>
            <p className="text-xs text-white/50 mt-0.5">
              Pick a motion preset for this section.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/8 text-white/70 hover:text-white transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {presetsQuery.isLoading ? (
            <div className="text-center text-white/50 py-10 text-sm">Loading…</div>
          ) : (
            <>
              {/* Tier 1 — Entry */}
              <TierAccordion
                title="Entry — fade in on scroll"
                count={entryPresets.length}
                open={entryOpen}
                onToggle={() => setEntryOpen(v => !v)}
              >
                <div className="grid grid-cols-2 gap-2.5">
                  {entryPresets.map(p => (
                    <PresetCard
                      key={p.id}
                      preset={p}
                      selected={selectedId === p.id}
                      onClick={() => handleSelect(p)}
                    />
                  ))}
                </div>
              </TierAccordion>

              {/* Tier 2 — Scroll-driven */}
              <TierAccordion
                title="Scroll-driven — animates with scroll"
                count={scrubPresets.length}
                open={scrubOpen}
                onToggle={() => setScrubOpen(v => !v)}
              >
                <div className="grid grid-cols-2 gap-2.5">
                  {scrubPresets.map(p => (
                    <PresetCard
                      key={p.id}
                      preset={p}
                      selected={selectedId === p.id}
                      onClick={() => handleSelect(p)}
                    />
                  ))}
                </div>
              </TierAccordion>

              {/* Config panel — visible when a Tier 1/2 preset is selected */}
              {selectedPreset && (
                <ConfigPanel
                  preset={selectedPreset}
                  config={config}
                  onChange={setConfig}
                />
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-t border-white/10">
          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              disabled={applyMut.isPending}
              className="ap-reset-button"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Reset to variant default
            </button>
            <button
              onClick={handleNone}
              disabled={applyMut.isPending}
              className="ap-reset-button"
            >
              No animation
            </button>
          </div>
          {/* Replay button — visible when a real preset is selected.
              Triggers in-place replay in the section iframe without
              re-PATCHing. 4B.1 closes the 3-step verify loop down to
              1 step. */}
          {selectedPreset && onReplay && (
            <button
              onClick={onReplay}
              className="ap-reset-button"
              title="Play the animation again in the editor"
            >
              <RotateCw className="h-3.5 w-3.5" /> Replay
            </button>
          )}
        </div>
      </div>
    </div>
  )
}


function TierAccordion({
  title, count, open, onToggle, children,
}: {
  title: string
  count: number
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="mb-2">
      <button onClick={onToggle} className="ap-tier-header w-full">
        <div className="flex items-center gap-2">
          {open
            ? <ChevronUp className="h-3.5 w-3.5 text-white/50" />
            : <ChevronDown className="h-3.5 w-3.5 text-white/50" />}
          <span className="ap-tier-title">{title}</span>
        </div>
        <span className="ap-tier-count">{count}</span>
      </button>
      {open && <div className="pt-1">{children}</div>}
    </div>
  )
}


function PresetCard({
  preset, selected, onClick,
}: {
  preset: PresetRow
  selected: boolean
  onClick: () => void
}) {
  // stagger_children and pin_and_scrub need extra preview bars
  const needsExtraBars =
    preset.id === 'stagger_children' || preset.id === 'pin_and_scrub'
  return (
    <button
      onClick={onClick}
      className={`ap-card ${selected ? 'selected' : ''}`}
    >
      {selected && (
        <span className="ap-card-check">
          <Check className="h-3 w-3" strokeWidth={3} />
        </span>
      )}
      <div className={`ap-preview-box ap-anim-${preset.id}`}>
        {needsExtraBars && <div className="ap-preview-bar-3" />}
        <div className="ap-preview-bar" />
        {needsExtraBars && <div className="ap-preview-bar-2" />}
      </div>
      <div>
        <div className="ap-card-title">{preset.display_name}</div>
        <div className="ap-card-desc">{preset.description}</div>
      </div>
    </button>
  )
}


function ConfigPanel({
  preset, config, onChange,
}: {
  preset: PresetRow
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
}) {
  const update = (key: string, value: unknown) =>
    onChange({ ...config, [key]: value })

  const isScrub = preset.tier === 'scrub'

  return (
    <div className="ap-config-panel">
      <div className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-1">
        Fine-tune
      </div>
      {!isScrub && (
        <>
          <ConfigSlider
            label="Duration"
            value={Number(config.duration ?? preset.defaults.duration ?? 0.8)}
            min={0.2} max={2} step={0.1} unit="s"
            onChange={(v) => update('duration', v)}
          />
          <ConfigSlider
            label="Delay"
            value={Number(config.delay ?? preset.defaults.delay ?? 0)}
            min={0} max={1} step={0.05} unit="s"
            onChange={(v) => update('delay', v)}
          />
          <ConfigSlider
            label="Stagger"
            value={Number(config.stagger ?? preset.defaults.stagger ?? 0)}
            min={0} max={0.5} step={0.02} unit="s"
            onChange={(v) => update('stagger', v)}
          />
          <div className="ap-config-row">
            <span className="ap-config-label">Ease</span>
            <select
              value={String(config.ease ?? preset.defaults.ease ?? 'power2.out')}
              onChange={(e) => update('ease', e.target.value)}
              className="ap-config-select"
            >
              {EASE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </>
      )}
      {isScrub && (
        <>
          <ConfigSlider
            label="Intensity"
            value={Number(config.intensity ?? preset.defaults.intensity ?? 1)}
            min={0.1} max={2} step={0.1} unit="×"
            onChange={(v) => update('intensity', v)}
          />
          <div className="ap-config-checkbox-row">
            <input
              id="ap-mobile-mode"
              type="checkbox"
              checked={(config.mobile_mode ?? preset.defaults.mobile_mode ?? 'auto') === 'auto'}
              onChange={(e) => update('mobile_mode', e.target.checked ? 'auto' : 'disable')}
            />
            <label htmlFor="ap-mobile-mode">
              Reduce on mobile <span className="text-white/40">(auto-degrade scrub on &lt;768px)</span>
            </label>
          </div>
        </>
      )}
    </div>
  )
}


function ConfigSlider({
  label, value, min, max, step, unit, onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  onChange: (v: number) => void
}) {
  return (
    <div className="ap-config-row">
      <span className="ap-config-label">{label}</span>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="ap-config-input"
      />
      <span className="ap-config-value">
        {value.toFixed(step < 1 ? (step < 0.1 ? 2 : 1) : 0)}{unit}
      </span>
    </div>
  )
}
