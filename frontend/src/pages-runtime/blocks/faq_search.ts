import { t } from '../api'

/**
 * FAQ with search. Template contract: [data-faq-search] input,
 * [data-faq-item] entries (question + answer text), optional
 * [data-faq-empty] message. Root gets data-faq-search-root.
 */
export function initFaqSearch(root: HTMLElement): void {
  const input = root.querySelector<HTMLInputElement>('[data-faq-search]')
  const items = Array.from(root.querySelectorAll<HTMLElement>('[data-faq-item]'))
  if (!input || items.length === 0) return
  root.setAttribute('data-faq-search-root', '')
  let empty = root.querySelector<HTMLElement>('[data-faq-empty]')
  if (!empty) {
    empty = document.createElement('p'); empty.setAttribute('data-faq-empty', ''); empty.textContent = t('noResults')
    items[items.length - 1].insertAdjacentElement('afterend', empty)
  }
  const norm = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  const texts = items.map(i => norm(i.textContent || ''))
  const filter = () => {
    const q = norm(input.value.trim())
    let shown = 0
    items.forEach((it, i) => { const hit = !q || texts[i].includes(q); it.hidden = !hit; if (hit) shown++ })
    root.setAttribute('data-empty', shown === 0 ? '1' : '0')
  }
  input.addEventListener('input', filter)
  filter()
}
