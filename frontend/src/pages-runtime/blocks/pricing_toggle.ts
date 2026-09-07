/**
 * Monthly / annual pricing toggle.
 * Template contract: [data-pricing-toggle] (checkbox or two buttons with
 * data-period="monthly|annual"); prices carry data-price-monthly and
 * data-price-annual (display strings); optional [data-period-label].
 */
export function initPricingToggle(root: HTMLElement): void {
  const prices = Array.from(root.querySelectorAll<HTMLElement>('[data-price-monthly]'))
  const labels = Array.from(root.querySelectorAll<HTMLElement>('[data-period-label]'))
  const apply = (period: 'monthly' | 'annual') => {
    root.setAttribute('data-period', period)
    prices.forEach(p => {
      const v = p.getAttribute(period === 'annual' ? 'data-price-annual' : 'data-price-monthly')
      if (v != null) p.textContent = v
    })
    labels.forEach(l => {
      const v = l.getAttribute(period === 'annual' ? 'data-label-annual' : 'data-label-monthly')
      if (v != null) l.textContent = v
    })
    root.querySelectorAll<HTMLElement>('[data-period]').forEach(b => {
      if (b === root) return
      b.setAttribute('aria-pressed', String(b.getAttribute('data-period') === period))
    })
  }
  root.querySelectorAll<HTMLElement>('[data-pricing-toggle]').forEach(tg => {
    if (tg instanceof HTMLInputElement && tg.type === 'checkbox') {
      tg.addEventListener('change', () => apply(tg.checked ? 'annual' : 'monthly'))
    }
  })
  root.querySelectorAll<HTMLElement>('button[data-period]').forEach(b => {
    b.addEventListener('click', () => apply(b.getAttribute('data-period') === 'annual' ? 'annual' : 'monthly'))
  })
  apply((root.getAttribute('data-period') as 'monthly' | 'annual') || 'monthly')
}
