/**
 * VariantPickerModal — 2-step picker for adding sections or swapping
 * a section's variant.
 *
 * Step 1: category grid (12 categories, Liquid Glass cards).
 * Step 2: variant grid for the chosen category (4+ variants per
 *         category, shown as thumbnail cards with name + description).
 *
 * Triggered from:
 *   - "+ Add Section" sticky button → onPick adds a new section
 *   - Section hover bar ⟳ icon → onPick swaps the variant in place
 *
 * Categories with no seeded variants (everything except Hero in
 * Commit 2) show a "Coming soon" empty state.
 */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X, ChevronLeft, Search,
  Layout, Grid3x3, BadgeDollarSign, Quote, Zap, HelpCircle,
  Users, BarChart3, Mail, LayoutTemplate, Image as ImageIcon,
  Hexagon,
  PanelTop,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { pagesApi } from '@/api/pages'
import './section-editor.css'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

interface Variant {
  id: string
  category: string
  variant_id: string
  display_name: string
  description: string | null
  preview_thumbnail_url: string | null
  svg_thumbnail: string | null
  default_props: Record<string, unknown>
}

interface VariantsResponse {
  data: Variant[]
}

interface Props {
  open: boolean
  /** "add" = new section at end; "swap" = change existing variant */
  mode: 'add' | 'swap'
  /** When mode='swap', restrict to the existing section's category. */
  lockedCategory?: string
  onClose: () => void
  onPick: (variant: Variant) => void
}

interface CategoryDef {
  value: string
  label: string
  subtitle: string
  Icon: LucideIcon
  /** CSS linear-gradient string for the icon container background. */
  gradient: string
}

// Each category has a unique gradient that previews the vibe of the
// section type. Gradients use the OCIDM palette: electric-blue
// #00D4FF, violet #8B5CF6, magenta #EC4899, plus warm/cool extensions.
const CATEGORIES: CategoryDef[] = [
  // `nav` was missing here, which made the 3 seeded navbar variants
  // unreachable from the picker (they only appeared via auto-prepend).
  { value: 'nav',          label: i18n.t('ui:VariantPickerModal.navbar'),       subtitle: i18n.t('ui:VariantPickerModal.stickyHeadersAndMenus'),          Icon: PanelTop,         gradient: 'linear-gradient(135deg, #475569, #00D4FF)' },
  { value: 'hero',         label: i18n.t('ui:VariantPickerModal.hero'),         subtitle: i18n.t('ui:VariantPickerModal.aboveTheFoldAttentionGrabbers'),  Icon: Layout,           gradient: 'linear-gradient(135deg, #00D4FF, #8B5CF6)' },
  { value: 'features',     label: i18n.t('ui:VariantPickerModal.features'),     subtitle: i18n.t('ui:VariantPickerModal.showcaseCapabilitiesBenefits'),   Icon: Grid3x3,          gradient: 'linear-gradient(135deg, #8B5CF6, #EC4899)' },
  { value: 'pricing',      label: i18n.t('ui:VariantPickerModal.pricing'),      subtitle: i18n.t('ui:VariantPickerModal.plansTiersAndPackages'),         Icon: BadgeDollarSign,  gradient: 'linear-gradient(135deg, #EC4899, #F59E0B)' },
  { value: 'testimonials', label: i18n.t('ui:VariantPickerModal.testimonials'), subtitle: i18n.t('ui:VariantPickerModal.socialProofAndQuotes'),            Icon: Quote,            gradient: 'linear-gradient(135deg, #06B6D4, #8B5CF6)' },
  { value: 'cta',          label: 'CTA',          subtitle: i18n.t('ui:VariantPickerModal.actionDrivingCallOuts'),           Icon: Zap,              gradient: 'linear-gradient(135deg, #F59E0B, #EC4899)' },
  { value: 'faq',          label: 'FAQ',          subtitle: i18n.t('ui:VariantPickerModal.commonQuestionsAnswered'),          Icon: HelpCircle,       gradient: 'linear-gradient(135deg, #6366F1, #8B5CF6)' },
  { value: 'team',         label: i18n.t('ui:VariantPickerModal.team'),         subtitle: i18n.t('ui:VariantPickerModal.peopleBehindTheBrand'),            Icon: Users,            gradient: 'linear-gradient(135deg, #10B981, #06B6D4)' },
  { value: 'stats',        label: i18n.t('ui:VariantPickerModal.stats'),        subtitle: i18n.t('ui:VariantPickerModal.numbersThatBuildCredibility'),     Icon: BarChart3,        gradient: 'linear-gradient(135deg, #00D4FF, #10B981)' },
  { value: 'contact',      label: i18n.t('ui:VariantPickerModal.contact'),      subtitle: i18n.t('ui:VariantPickerModal.reachOutPathsAndForms'),          Icon: Mail,             gradient: 'linear-gradient(135deg, #8B5CF6, #06B6D4)' },
  { value: 'footer',       label: i18n.t('ui:VariantPickerModal.footer'),       subtitle: i18n.t('ui:VariantPickerModal.closingStructureAndLinks'),        Icon: LayoutTemplate,   gradient: 'linear-gradient(135deg, #475569, #8B5CF6)' },
  { value: 'gallery',      label: i18n.t('ui:VariantPickerModal.gallery'),      subtitle: i18n.t('ui:VariantPickerModal.imageVideoShowcases'),            Icon: ImageIcon,        gradient: 'linear-gradient(135deg, #EC4899, #8B5CF6)' },
  { value: 'logos',        label: i18n.t('ui:VariantPickerModal.logos'),        subtitle: i18n.t('ui:VariantPickerModal.brandWallsAndTrustMarks'),        Icon: Hexagon,          gradient: 'linear-gradient(135deg, #06B6D4, #6366F1)' },
]

export default function VariantPickerModal({ open, mode, lockedCategory, onClose, onPick }: Props) {
  const { t } = useTranslation('ui')
  const [category, setCategory] = useState<string | null>(lockedCategory ?? null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!open) {
      // Reset on close
      setCategory(lockedCategory ?? null)
      setFilter('')
    } else if (lockedCategory) {
      setCategory(lockedCategory)
    }
  }, [open, lockedCategory])

  // Fetch variants for the selected category. Skips fetch until a
  // category is picked (step 1 → step 2 transition).
  const variantsQuery = useQuery<VariantsResponse>({
    queryKey: ['section-variants', category],
    queryFn: () => pagesApi.listVariants(category!) as Promise<VariantsResponse>,
    enabled: open && !!category,
    staleTime: 60_000,
  })

  const variants = variantsQuery.data?.data ?? []
  const filtered = useMemo(() => {
    if (!filter.trim()) return variants
    const q = filter.toLowerCase()
    return variants.filter(
      v => v.display_name.toLowerCase().includes(q)
        || (v.description || '').toLowerCase().includes(q),
    )
  }, [variants, filter])

  if (!open) return null

  const showingCategoryGrid = category === null

  return (
    <div
      className="se-root fixed inset-0 z-50 flex items-center justify-center p-4 se-picker-backdrop"
      onClick={onClose}
    >
      <div
        className="se-picker-surface w-full max-w-4xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-2 min-w-0">
            {!showingCategoryGrid && !lockedCategory && (
              <button
                onClick={() => setCategory(null)}
                className="p-1.5 rounded-md hover:bg-white/8 text-white/68 hover:text-white/96 transition-colors"
                title={t('ui:VariantPickerModal.backToCategories')}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
            <div>
              <h2 className="text-base font-semibold text-white/96">
                {showingCategoryGrid
                  ? (mode === 'add' ? t('ui:VariantPickerModal.addASection') : t('ui:VariantPickerModal.changeVariant'))
                  : t('ui:VariantPickerModal.v0Variants', { v0: CATEGORIES.find(c => c.value === category)?.label || category })}
              </h2>
              <p className="text-xs text-white/46 mt-0.5">
                {showingCategoryGrid
                  ? t('ui:VariantPickerModal.pickACategoryToSee')
                  : t('ui:VariantPickerModal.clickAnyLayoutToApply')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/8 text-white/68 hover:text-white/96 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Filter (only on variant grid) */}
        {!showingCategoryGrid && (
          <div className="px-6 py-3 border-b border-white/10">
            <div className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-lg">
              <Search className="h-3.5 w-3.5 text-white/46" />
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder={t('ui:VariantPickerModal.searchThisCategory')}
                className="flex-1 bg-transparent text-sm text-white/96 placeholder:text-white/46 outline-none"
              />
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {showingCategoryGrid ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  onClick={() => setCategory(cat.value)}
                  className="se-category-card group"
                >
                  <div
                    className="se-category-card-icon"
                    style={{ backgroundImage: cat.gradient }}
                  >
                    <cat.Icon className="h-7 w-7 text-white drop-shadow-sm" strokeWidth={1.75} />
                  </div>
                  <div className="se-category-card-title">{cat.label}</div>
                  <div className="se-category-card-subtitle">{cat.subtitle}</div>
                </button>
              ))}
            </div>
          ) : variantsQuery.isLoading ? (
            <div className="text-center text-white/46 py-12">
              <p className="text-sm">{t('ui:VariantPickerModal.loadingVariants')}</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-white/46">
                {variants.length === 0
                  ? t('ui:VariantPickerModal.noVariantsSeededForThis')
                  : t('ui:VariantPickerModal.noVariantsMatchFilter', { filter })}
              </p>
              {variants.length === 0 && (
                <p className="text-xs text-white/30 mt-2">
                 {t('ui:VariantPickerModal.heroVariantsAreAvailableIn')}
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((v) => (
                <button
                  key={v.id}
                  onClick={() => onPick(v)}
                  className="se-picker-card"
                >
                  <div className="se-picker-card-thumb">
                    {v.svg_thumbnail ? (
                      // Inline SVG schematic — hand-designed per variant,
                      // Liquid Glass palette. Self-contained (no remote
                      // refs). dangerouslySetInnerHTML is safe here:
                      // svg_thumbnail comes from our seed file, not user
                      // input.
                      <div
                        className="w-full h-full"
                        // eslint-disable-next-line react/no-danger
                        dangerouslySetInnerHTML={{ __html: v.svg_thumbnail }}
                      />
                    ) : v.preview_thumbnail_url ? (
                      <img
                        src={v.preview_thumbnail_url}
                        alt={v.display_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span>{v.display_name}</span>
                    )}
                  </div>
                  <div className="se-picker-card-title">{v.display_name}</div>
                  {v.description && (
                    <div className="se-picker-card-desc">{v.description}</div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
