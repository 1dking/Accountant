/**
 * Pages runtime — behaviour for dynamic blocks on published pages.
 *
 * Plain TypeScript, no framework. Built as an IIFE by
 * frontend/vite.runtime.config.ts into
 * backend/app/pages/static/runtime/<version>/runtime.{js,css} and linked
 * by compile_page() only when a page contains a block with a behaviour
 * or a CSS motion preset.
 *
 * Contract: every dynamic block's <section> wrapper carries
 *   data-block="<behaviour id>"  data-block-config='{…runtime fields…}'
 * and the page exposes window.__PAGES__ = { slug, api, locale, version }.
 */
import './runtime.css'
import { RUNTIME_VERSION } from './version'
import { initLeadForm } from './blocks/lead_form'
import { initQuoteCalc } from './blocks/quote_calc'
import { initBookingPicker } from './blocks/booking_picker'
import { initPricingToggle } from './blocks/pricing_toggle'
import { initCountUp } from './blocks/count_up'
import { initCountdown } from './blocks/countdown'
import { initBeforeAfter } from './blocks/before_after'
import { initFaqSearch } from './blocks/faq_search'
import { initStickyBar } from './blocks/sticky_bar'
import { initOpenNow } from './blocks/open_now'
import { initMarquee } from './blocks/marquee'
import { initMotionFallback } from './blocks/motion'

export type BlockInit = (root: HTMLElement) => void | (() => void)

const REGISTRY: Record<string, BlockInit> = {
  lead_form: initLeadForm,
  quote_calc: initQuoteCalc,
  booking_picker: initBookingPicker,
  pricing_toggle: initPricingToggle,
  count_up: initCountUp,
  countdown: initCountdown,
  before_after: initBeforeAfter,
  faq_search: initFaqSearch,
  sticky_bar: initStickyBar,
  open_now: initOpenNow,
  marquee: initMarquee,
}

function boot(): void {
  document.querySelectorAll<HTMLElement>('[data-block]').forEach(el => {
    const id = el.getAttribute('data-block') || ''
    const init = REGISTRY[id]
    if (!init) return
    try {
      init(el)
      el.setAttribute('data-block-ready', '1')
    } catch (err) {
      console.warn('[pages-runtime] block init failed', id, err)
    }
  })
  initMotionFallback()
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot)
else boot()

// Exposed for debugging / the editor preview.
;(window as unknown as { PagesRuntime: unknown }).PagesRuntime = { version: RUNTIME_VERSION, boot, blocks: Object.keys(REGISTRY) }
