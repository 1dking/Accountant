/**
 * Count-up numbers. Template contract: [data-count-to="250"] with optional
 * data-count-prefix / data-count-suffix / data-count-decimals. Runs once
 * when the element scrolls into view; honours reduced motion.
 */
export function initCountUp(root: HTMLElement): void {
  const els = Array.from(root.querySelectorAll<HTMLElement>('[data-count-to]'))
  if (els.length === 0) return
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
  const fmt = (n: number, dec: number) => n.toLocaleString(document.documentElement.lang || 'en', { minimumFractionDigits: dec, maximumFractionDigits: dec })
  const run = (el: HTMLElement) => {
    const raw = el.getAttribute('data-count-to') || '0'
    const target = Number(raw) || 0
    // Decimals: explicit attribute, else inferred from the value ("99.9" → 1).
    const decAttr = el.getAttribute('data-count-decimals')
    const dec = decAttr != null ? Number(decAttr) || 0 : (raw.split('.')[1]?.length ?? 0)
    const pre = el.getAttribute('data-count-prefix') || ''
    const suf = el.getAttribute('data-count-suffix') || ''
    if (reduce) { el.textContent = pre + fmt(target, dec) + suf; return }
    const dur = 1400
    const start = performance.now()
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / dur)
      const eased = 1 - Math.pow(1 - p, 3)
      el.textContent = pre + fmt(target * eased, dec) + suf
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }
  if (!('IntersectionObserver' in window)) { els.forEach(run); return }
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { run(e.target as HTMLElement); io.unobserve(e.target) } })
  }, { threshold: 0.4 })
  els.forEach(el => io.observe(el))
}
