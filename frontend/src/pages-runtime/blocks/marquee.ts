/**
 * Marquee: the CSS preset (css_marquee) animates [data-marquee] by -50%;
 * for a seamless loop the runtime duplicates the track's children once.
 */
export function initMarquee(root: HTMLElement): void {
  root.querySelectorAll<HTMLElement>('[data-marquee]').forEach(track => {
    if (track.getAttribute('data-marquee-cloned')) return
    const kids = Array.from(track.children)
    kids.forEach(k => { const c = k.cloneNode(true) as HTMLElement; c.setAttribute('aria-hidden', 'true'); track.appendChild(c) })
    track.setAttribute('data-marquee-cloned', '1')
  })
}
