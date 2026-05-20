/**
 * VariantPickerModal — 2-step picker for SectionEditor.
 *
 * Covers:
 *  - test_variant_picker_opens_on_add_section_click (category grid
 *    rendered on initial open in 'add' mode, all 12 categories)
 *  - test_variant_picker_swaps_variant_on_existing_section ('swap'
 *    mode skips the category grid because lockedCategory is set;
 *    onPick fires with the chosen variant)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import VariantPickerModal from '@/components/pages/VariantPickerModal'

// Mock the API call — VariantPickerModal calls pagesApi.listVariants
vi.mock('@/api/pages', () => ({
  pagesApi: {
    listVariants: vi.fn(async (category?: string) => {
      if (category === 'hero') {
        return {
          data: [
            {
              id: 'var_hero_video',
              category: 'hero',
              variant_id: 'hero_video',
              display_name: 'Video Background',
              description: 'Full-screen video background with text overlay',
              preview_thumbnail_url: null,
              default_props: {},
            },
            {
              id: 'var_hero_two_col_image',
              category: 'hero',
              variant_id: 'hero_two_col_image',
              display_name: 'Two-Column with Image',
              description: 'Copy left, image right',
              preview_thumbnail_url: null,
              default_props: {},
            },
          ],
        }
      }
      return { data: [] }
    }),
  },
}))

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('VariantPickerModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens on add mode showing the 12 category grid', () => {
    renderWithQueryClient(
      <VariantPickerModal open mode="add" onClose={() => {}} onPick={() => {}} />,
    )
    // Header reflects "Add a section" mode
    expect(screen.getByText(/add a section/i)).toBeInTheDocument()
    // All 12 categories rendered as cards
    const expectedCategories = [
      'Hero', 'Features', 'Pricing', 'Testimonials',
      'CTA', 'FAQ', 'Team', 'Stats',
      'Contact', 'Footer', 'Gallery', 'Logos',
    ]
    for (const label of expectedCategories) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('swap mode with lockedCategory shows variant grid directly + onPick fires with chosen variant', async () => {
    const onPick = vi.fn()
    renderWithQueryClient(
      <VariantPickerModal
        open
        mode="swap"
        lockedCategory="hero"
        onClose={() => {}}
        onPick={onPick}
      />,
    )
    // Skips category grid — header says "Hero variants"
    expect(await screen.findByText(/hero variants/i)).toBeInTheDocument()
    // Variant cards loaded from the mocked API. The display name
    // appears twice (thumb fallback + title) when there's no preview
    // image — click the title element.
    const titles = await screen.findAllByText('Two-Column with Image')
    expect(titles.length).toBeGreaterThan(0)
    await userEvent.click(titles[titles.length - 1])
    await waitFor(() => {
      expect(onPick).toHaveBeenCalledTimes(1)
    })
    expect(onPick).toHaveBeenCalledWith(
      expect.objectContaining({
        variant_id: 'hero_two_col_image',
        category: 'hero',
      }),
    )
  })
})
