import { blockConfig, getJSON, pagesConfig, postJSON, t } from '../api'

/**
 * Inline booking picker. Config: CALENDAR_SLUG (text), DAYS (number).
 * Template contract: a [data-booking] container the runtime renders into.
 */
interface Cfg { CALENDAR_SLUG?: string; DAYS?: number | string }
interface Availability {
  data: {
    calendar: { slug: string; name: string; duration_minutes: number; timezone: string; description?: string | null }
    days: { date: string; slots: string[] }[]
  }
}

export function initBookingPicker(root: HTMLElement): void {
  const cfg = blockConfig<Cfg>(root)
  const mount = root.querySelector<HTMLElement>('[data-booking]')
  if (!mount) return
  const calendar = String(cfg.CALENDAR_SLUG || mount.getAttribute('data-calendar') || '').trim()
  const days = Math.min(31, Math.max(1, Number(cfg.DAYS) || 7))
  if (!calendar) { mount.innerHTML = `<p class="pg-muted">Calendar not configured.</p>`; return }

  const locale = pagesConfig().locale
  const fmtDay = new Intl.DateTimeFormat(locale, { weekday: 'short' })
  const fmtDate = new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' })
  const fmtTime = new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit' })
  const fmtFull = new Intl.DateTimeFormat(locale, { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })

  let avail: Availability['data'] | null = null
  let selectedDay = 0
  let selectedSlot: string | null = null

  const el = (html: string) => { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstElementChild as HTMLElement }

  const render = () => {
    if (!avail) return
    mount.innerHTML = ''
    const daysRow = el('<div class="pg-days" role="tablist"></div>')
    avail.days.forEach((d, i) => {
      const date = new Date(d.date + 'T12:00:00')
      const b = el(`<button type="button" class="pg-day" role="tab"><small>${fmtDay.format(date)}</small>${fmtDate.format(date)}</button>`) as HTMLButtonElement
      b.setAttribute('aria-selected', String(i === selectedDay))
      b.disabled = d.slots.length === 0
      b.addEventListener('click', () => { selectedDay = i; selectedSlot = null; render() })
      daysRow.appendChild(b)
    })
    mount.appendChild(daysRow)

    const day = avail.days[selectedDay]
    const slots = el('<div class="pg-slots"></div>')
    if (!day || day.slots.length === 0) {
      slots.appendChild(el(`<p class="pg-muted">${t('noSlots')}</p>`))
    } else {
      day.slots.forEach(iso => {
        const b = el(`<button type="button" class="pg-slot">${fmtTime.format(new Date(iso))}</button>`)
        b.setAttribute('aria-selected', String(iso === selectedSlot))
        b.addEventListener('click', () => { selectedSlot = iso; render() })
        slots.appendChild(b)
      })
    }
    mount.appendChild(slots)

    if (selectedSlot) {
      const form = el(`
        <form class="pg-form">
          <p class="pg-muted"><strong>${fmtFull.format(new Date(selectedSlot))}</strong> · ${avail.calendar.duration_minutes} min</p>
          <input name="guest_name" required placeholder="${t('name')}" autocomplete="name">
          <input name="guest_email" type="email" required placeholder="${t('email')}" autocomplete="email">
          <input name="guest_phone" type="tel" placeholder="${t('phone')}" autocomplete="tel">
          <textarea name="guest_notes" rows="2" placeholder="${t('notes')}"></textarea>
          <p class="pg-error" data-err></p>
          <div class="pg-actions">
            <button type="submit" class="pg-btn">${t('confirm')}</button>
            <button type="button" class="pg-link" data-back>${t('back')}</button>
          </div>
        </form>`) as HTMLFormElement
      form.querySelector('[data-back]')!.addEventListener('click', () => { selectedSlot = null; render() })
      form.addEventListener('submit', async ev => {
        ev.preventDefault()
        const err = form.querySelector<HTMLElement>('[data-err]')!
        err.textContent = ''
        const btn = form.querySelector<HTMLButtonElement>('button[type=submit]')!
        btn.disabled = true; btn.textContent = t('booking')
        const fd = new FormData(form)
        try {
          const res = await postJSON<{ data: { start_time: string; calendar: string; confirmation_message?: string | null } }>('/book', {
            calendar, start_time: selectedSlot,
            guest_name: fd.get('guest_name'), guest_email: fd.get('guest_email'),
            guest_phone: fd.get('guest_phone') || null, guest_notes: fd.get('guest_notes') || null,
          })
          mount.innerHTML = ''
          mount.appendChild(el(`<div class="pg-done"><strong>${t('booked')}</strong><br>${fmtFull.format(new Date(res.data.start_time))}${res.data.confirmation_message ? `<p class="pg-muted">${escapeHtml(res.data.confirmation_message)}</p>` : ''}</div>`))
          root.dispatchEvent(new CustomEvent('pages:booked', { bubbles: true, detail: res.data }))
        } catch (e) {
          err.textContent = (e as Error).message || t('failed')
          btn.disabled = false; btn.textContent = t('confirm')
        }
      })
      mount.appendChild(form)
    } else {
      mount.appendChild(el(`<p class="pg-muted">${t('pickTime')}</p>`))
    }
  }

  mount.innerHTML = `<p class="pg-muted">…</p>`
  getJSON<Availability>(`/data/availability?calendar=${encodeURIComponent(calendar)}&days=${days}`)
    .then(res => {
      avail = res.data
      const first = avail.days.findIndex(d => d.slots.length > 0)
      selectedDay = first >= 0 ? first : 0
      render()
    })
    .catch(e => { mount.innerHTML = `<p class="pg-error">${escapeHtml((e as Error).message || t('failed'))}</p>` })
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!))
}
