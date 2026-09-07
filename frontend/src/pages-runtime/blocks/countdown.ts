import { blockConfig, t } from '../api'

/**
 * Countdown to a deadline. Config: DEADLINE (ISO date/datetime).
 * Template contract: [data-countdown] with [data-cd-days|hours|minutes|
 * seconds] number slots, [data-cd-live] wrapper and [data-cd-expired].
 */
interface Cfg { DEADLINE?: string }

export function initCountdown(root: HTMLElement): void {
  const cfg = blockConfig<Cfg>(root)
  const box = root.querySelector<HTMLElement>('[data-countdown]') || root
  const raw = String(cfg.DEADLINE || box.getAttribute('data-deadline') || '')
  const deadline = new Date(raw.length <= 10 ? `${raw}T23:59:59` : raw)
  if (Number.isNaN(deadline.getTime())) return
  const slot = (k: string) => box.querySelector<HTMLElement>(`[data-cd-${k}]`)
  const d = slot('days'), h = slot('hours'), m = slot('minutes'), s = slot('seconds')
  const pad = (n: number) => String(n).padStart(2, '0')
  const expiredEl = box.querySelector<HTMLElement>('[data-cd-expired]')
  if (expiredEl && !expiredEl.textContent?.trim()) expiredEl.textContent = t('expired')
  const tick = () => {
    const diff = deadline.getTime() - Date.now()
    if (diff <= 0) { box.setAttribute('data-expired', '1'); clearInterval(timer); return }
    const secs = Math.floor(diff / 1000)
    if (d) d.textContent = String(Math.floor(secs / 86400))
    if (h) h.textContent = pad(Math.floor((secs % 86400) / 3600))
    if (m) m.textContent = pad(Math.floor((secs % 3600) / 60))
    if (s) s.textContent = pad(secs % 60)
  }
  const timer = setInterval(tick, 1000)
  tick()
}
