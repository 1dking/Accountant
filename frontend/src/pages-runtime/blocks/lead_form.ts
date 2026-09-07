import { postJSON, t } from '../api'

/**
 * Lead form. Template contract:
 *   <form data-lead-form> …inputs with name=… <button type="submit">
 *   [data-error] (optional) [data-success] (sibling, shown after submit)
 * The runtime adds the honeypot + time-on-page fields and posts to /lead.
 */
export function initLeadForm(root: HTMLElement): void {
  root.querySelectorAll<HTMLFormElement>('form[data-lead-form]').forEach(form => wireLeadForm(root, form))
}

export function wireLeadForm(
  root: HTMLElement,
  form: HTMLFormElement,
  extra?: () => Record<string, unknown>,
): void {
  const started = performance.now()
  if (!form.querySelector('[data-hp]')) {
    const hp = document.createElement('input')
    hp.type = 'text'; hp.name = '_hp'; hp.tabIndex = -1; hp.autocomplete = 'off'
    hp.setAttribute('data-hp', ''); hp.setAttribute('aria-hidden', 'true')
    form.appendChild(hp)
  }
  let errorEl = form.querySelector<HTMLElement>('[data-error]')
  if (!errorEl) {
    errorEl = document.createElement('p'); errorEl.setAttribute('data-error', '')
    form.appendChild(errorEl)
  }
  form.setAttribute('novalidate', '')
  form.addEventListener('submit', async ev => {
    ev.preventDefault()
    errorEl!.textContent = ''
    if (!form.checkValidity()) { form.reportValidity(); return }
    const data: Record<string, unknown> = {}
    new FormData(form).forEach((v, k) => { if (typeof v === 'string') data[k] = v })
    data._t = Math.round(performance.now() - started)
    data._block = root.getAttribute('data-block') || 'lead_form'
    if (extra) Object.assign(data, extra())
    const btn = form.querySelector<HTMLButtonElement>('button[type="submit"]')
    const label = btn?.textContent
    form.setAttribute('data-state', 'sending')
    if (btn) btn.textContent = t('sending')
    try {
      await postJSON('/lead', data)
      root.setAttribute('data-done', '1')
      const ok = root.querySelector<HTMLElement>('[data-success]')
      if (ok) { ok.hidden = false; ok.style.display = 'block' }
      else { const p = document.createElement('p'); p.textContent = t('sent'); form.replaceWith(p) }
      root.dispatchEvent(new CustomEvent('pages:lead', { bubbles: true, detail: data }))
    } catch (err) {
      errorEl!.textContent = (err as Error).message || t('failed')
    } finally {
      form.removeAttribute('data-state')
      if (btn && label) btn.textContent = label
    }
  })
}
