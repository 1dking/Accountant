/**
 * Sticky action bar: hidden until the visitor scrolls past the first
 * screen, then slides up. Template contract: [data-sticky-bar].
 */
export function initStickyBar(root: HTMLElement): void {
  const bar = root.querySelector<HTMLElement>('[data-sticky-bar]')
  if (!bar) return
  const threshold = Number(bar.getAttribute('data-show-after')) || Math.min(400, innerHeight * 0.6)
  const update = () => bar.classList.toggle('pg-visible', scrollY > threshold)
  addEventListener('scroll', update, { passive: true })
  update()
}
