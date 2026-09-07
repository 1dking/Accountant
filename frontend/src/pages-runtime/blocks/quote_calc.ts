import { blockConfig, money, t } from '../api'
import { wireLeadForm } from './lead_form'

/**
 * Instant quote calculator.
 * Config: BASE_PRICE (number), CURRENCY (text), items come from the DOM:
 *   [data-quote-item] input[type=number|checkbox|select] with
 *   data-price="12.5" data-label="Windows" (per unit) — checkbox = 0/1.
 *   [data-quote-total] shows the running total.
 *   form[data-lead-form] inside the block posts the lead with _quote.
 */
interface Cfg { BASE_PRICE?: number | string; CURRENCY?: string }

export function initQuoteCalc(root: HTMLElement): void {
  const cfg = blockConfig<Cfg>(root)
  const base = Number(cfg.BASE_PRICE ?? 0) || 0
  const currency = (cfg.CURRENCY || 'CAD').toUpperCase()
  const totalEl = root.querySelector<HTMLElement>('[data-quote-total]')
  const inputs = Array.from(root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-quote-item]'))

  const lines = () => inputs.map(inp => {
    const price = Number(inp.getAttribute('data-price') ?? (inp instanceof HTMLSelectElement ? inp.selectedOptions[0]?.getAttribute('data-price') : 0)) || 0
    let qty = 0
    if (inp instanceof HTMLInputElement && inp.type === 'checkbox') qty = inp.checked ? 1 : 0
    else if (inp instanceof HTMLSelectElement) qty = 1
    else qty = Math.max(0, Number(inp.value) || 0)
    const label = inp.getAttribute('data-label') || inp.name || 'item'
    return { label, qty, price, amount: Math.round(qty * price * 100) / 100 }
  })
  const compute = () => {
    const items = lines()
    const total = Math.round((base + items.reduce((s, l) => s + l.amount, 0)) * 100) / 100
    if (totalEl) totalEl.textContent = money(total, currency)
    root.setAttribute('data-quote-total-value', String(total))
    return { items: items.filter(l => l.qty > 0), total, currency, base }
  }
  inputs.forEach(inp => { inp.addEventListener('input', compute); inp.addEventListener('change', compute) })
  compute()
  if (totalEl && !totalEl.getAttribute('aria-label')) totalEl.setAttribute('aria-label', t('estimate'))

  const form = root.querySelector<HTMLFormElement>('form[data-lead-form]')
  if (form) wireLeadForm(root, form, () => ({ _quote: compute() }))
}
