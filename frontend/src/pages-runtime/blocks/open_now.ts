import { blockConfig, pagesConfig, t } from '../api'

/**
 * "Open now" badge from weekly hours. Config: HOURS (list of
 * {DAY: "monday"…, OPEN: "09:00", CLOSE: "17:00"}), TIMEZONE (IANA).
 * Template contract: [data-open-now] with [data-open-dot] and
 * [data-open-text]; the runtime sets data-open="1|0".
 */
interface Cfg { HOURS?: { DAY?: string; OPEN?: string; CLOSE?: string }[]; TIMEZONE?: string }
const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

export function initOpenNow(root: HTMLElement): void {
  const cfg = blockConfig<Cfg>(root)
  const box = root.querySelector<HTMLElement>('[data-open-now]')
  if (!box || !Array.isArray(cfg.HOURS)) return
  const tz = cfg.TIMEZONE || Intl.DateTimeFormat().resolvedOptions().timeZone
  const text = box.querySelector<HTMLElement>('[data-open-text]')
  const fmtTime = (hhmm: string) => {
    const [h, m] = hhmm.split(':').map(Number)
    const d = new Date(); d.setHours(h, m, 0, 0)
    return new Intl.DateTimeFormat(pagesConfig().locale, { hour: 'numeric', minute: '2-digit' }).format(d)
  }
  const update = () => {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'long', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date())
    const day = (parts.find(p => p.type === 'weekday')?.value || '').toLowerCase()
    const hh = Number(parts.find(p => p.type === 'hour')?.value) % 24
    const mm = Number(parts.find(p => p.type === 'minute')?.value)
    const now = hh * 60 + mm
    const toMin = (s?: string) => { const [h, m] = String(s || '0:0').split(':').map(Number); return h * 60 + (m || 0) }
    const today = (cfg.HOURS || []).filter(h => (h.DAY || '').toLowerCase() === day && h.OPEN && h.CLOSE)
    const openRange = today.find(h => now >= toMin(h.OPEN) && now < toMin(h.CLOSE))
    if (openRange) {
      box.setAttribute('data-open', '1')
      if (text) text.textContent = `${t('openNow')} · ${t('closesAt', { t: fmtTime(openRange.CLOSE!) })}`
      return
    }
    box.setAttribute('data-open', '0')
    const next = today.find(h => now < toMin(h.OPEN))
    if (text) text.textContent = next ? `${t('closedNow')} · ${t('opensAt', { t: fmtTime(next.OPEN!) })}` : t('closedNow')
    void DAYS
  }
  update()
  setInterval(update, 60_000)
}
