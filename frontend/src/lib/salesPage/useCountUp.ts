import { useEffect, useRef, useState } from 'react'

/**
 * Count from 0 to `target` the first time the element scrolls into view.
 * Ease-out so the last digits settle satisfyingly. Honors reduced motion by
 * jumping straight to the target — the FEATURE is the number, not the twitch.
 */
export function useCountUp(target: number, durationMs = 1400) {
  const ref = useRef<HTMLElement | null>(null)
  const [value, setValue] = useState(0)
  const fired = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting || fired.current) return
        fired.current = true
        observer.disconnect()

        if (reduced) {
          setValue(target)
          return
        }

        const start = performance.now()
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / durationMs)
          const eased = 1 - Math.pow(1 - t, 3)
          setValue(Math.round(target * eased))
          if (t < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      },
      { threshold: 0.4 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [target, durationMs])

  return { ref, value }
}
