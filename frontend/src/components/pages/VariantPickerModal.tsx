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
import { X, ChevronLeft, Search } from 'lucide-react'
import { pagesApi } from '@/api/pages'
import './section-editor.css'

interface Variant {
  id: string
  category: string
  variant_id: string
  display_name: string
  description: string | null
  preview_thumbnail_url: string | null
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

const CATEGORIES: { value: string; label: string; icon: string }[] = [
  { value: 'hero', label: 'Hero', icon: '🦸' },
  { value: 'features', label: 'Features', icon: '⭐' },
  { value: 'pricing', label: 'Pricing', icon: '💰' },
  { value: 'testimonials', label: 'Testimonials', icon: '💬' },
  { value: 'cta', label: 'CTA', icon: '🎯' },
  { value: 'faq', label: 'FAQ', icon: '❓' },
  { value: 'team', label: 'Team', icon: '👥' },
  { value: 'stats', label: 'Stats', icon: '📊' },
  { value: 'contact', label: 'Contact', icon: '📧' },
  { value: 'footer', label: 'Footer', icon: '📑' },
  { value: 'gallery', label: 'Gallery', icon: '🖼️' },
  { value: 'logos', label: 'Logos', icon: '🏢' },
]

export default function VariantPickerModal({ open, mode, lockedCategory, onClose, onPick }: Props) {
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
                title="Back to categories"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
            <div>
              <h2 className="text-base font-semibold text-white/96">
                {showingCategoryGrid
                  ? (mode === 'add' ? 'Add a section' : 'Change variant')
                  : `${CATEGORIES.find(c => c.value === category)?.label || category} variants`}
              </h2>
              <p className="text-xs text-white/46 mt-0.5">
                {showingCategoryGrid
                  ? 'Pick a category to see available layouts.'
                  : 'Click any layout to apply it.'}
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
                placeholder="Search this category..."
                className="flex-1 bg-transparent text-sm text-white/96 placeholder:text-white/46 outline-none"
              />
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {showingCategoryGrid ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  onClick={() => setCategory(cat.value)}
                  className="se-picker-card text-center py-6"
                >
                  <div className="text-2xl mb-2">{cat.icon}</div>
                  <div className="se-picker-card-title">{cat.label}</div>
                </button>
              ))}
            </div>
          ) : variantsQuery.isLoading ? (
            <div className="text-center text-white/46 py-12">
              <p className="text-sm">Loading variants…</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-white/46">
                {variants.length === 0
                  ? 'No variants seeded for this category yet — coming soon.'
                  : `No variants match "${filter}".`}
              </p>
              {variants.length === 0 && (
                <p className="text-xs text-white/30 mt-2">
                  Hero variants are available in Commit 2; the rest land in Commit 3.
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
                    {v.preview_thumbnail_url ? (
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
