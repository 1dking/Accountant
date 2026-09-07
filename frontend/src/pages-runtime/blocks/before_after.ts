/**
 * Before / after image slider. Template contract:
 *   <div data-before-after><img data-before><div data-after><img></div>
 *        <div data-handle></div><input type="range" min=0 max=100 value=50></div>
 * The runtime drives the --pg-cut CSS variable from the range input
 * (keyboard accessible for free) and from pointer drags.
 */
export function initBeforeAfter(root: HTMLElement): void {
  root.querySelectorAll<HTMLElement>('[data-before-after]').forEach(box => {
    let range = box.querySelector<HTMLInputElement>('input[type="range"]')
    if (!range) {
      range = document.createElement('input')
      range.type = 'range'; range.min = '0'; range.max = '100'; range.value = '50'
      range.setAttribute('aria-label', 'Compare before and after')
      box.appendChild(range)
    }
    if (!box.querySelector('[data-handle]')) {
      const h = document.createElement('div'); h.setAttribute('data-handle', ''); box.appendChild(h)
    }
    const set = (v: number) => { box.style.setProperty('--pg-cut', `${Math.max(0, Math.min(100, v))}%`); range!.value = String(v) }
    range.addEventListener('input', () => set(Number(range!.value)))
    box.addEventListener('pointermove', ev => {
      if (ev.buttons !== 1 && ev.pointerType !== 'touch') return
      const r = box.getBoundingClientRect()
      set(((ev.clientX - r.left) / r.width) * 100)
    })
    set(Number(range.value) || 50)
  })
}
