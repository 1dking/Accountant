/**
 * Fallback for browsers without CSS scroll-driven animations: toggle
 * .pg-in-view on [data-motion] sections via IntersectionObserver so the
 * @supports-not rules in runtime.css can transition them in.
 */
export function initMotionFallback(): void {
  if (CSS.supports('animation-timeline: view()')) return
  const els = Array.from(document.querySelectorAll<HTMLElement>('[data-motion]'))
  if (els.length === 0) return
  if (!('IntersectionObserver' in window)) { els.forEach(e => e.classList.add('pg-in-view')); return }
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('pg-in-view'); io.unobserve(e.target) } })
  }, { threshold: 0.15 })
  els.forEach(e => io.observe(e))
}
