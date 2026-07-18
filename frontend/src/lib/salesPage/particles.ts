/**
 * Hero particle field — thousands of glowing particles swirl in a dark void and,
 * driven by SCROLL PROGRESS (not time), assemble themselves into the outline of
 * a dashboard. The crisp DOM mockup crossfades in over the top as assembly
 * completes, so the "dashboard builds itself as the visitor scrolls".
 *
 * Deliberately hand-rolled on canvas 2D instead of scrubbing a video file:
 * scroll-scrubbing video seeks janky and ships megabytes; particles scrub
 * frame-perfectly at any resolution and cost nothing. No GSAP — progress comes
 * in via setProgress() from a passive scroll handler.
 *
 * Perf notes: glow is a pre-rendered radial-gradient sprite (drawImage), not
 * shadowBlur (which would melt frame rate at 2k+ particles). DPR is capped at
 * 1.75. The rAF loop only runs while the hero is on screen (start/stop).
 */

export interface NormRect {
  x: number
  y: number
  w: number
  h: number
}

/**
 * The dashboard layout in normalized [0..1] coordinates of the mockup box.
 * SHARED with the DOM mockup in SalesPage.tsx (positioned with the same
 * percentages) so the particle skeleton and the crisp DOM version align when
 * they crossfade. Change one, change both — that's why this is exported.
 */
export const MOCKUP_LAYOUT: Record<string, NormRect> = {
  sidebar: { x: 0.015, y: 0.02, w: 0.15, h: 0.96 },
  topbar: { x: 0.185, y: 0.02, w: 0.8, h: 0.075 },
  card1: { x: 0.185, y: 0.13, w: 0.252, h: 0.17 },
  card2: { x: 0.457, y: 0.13, w: 0.252, h: 0.17 },
  card3: { x: 0.729, y: 0.13, w: 0.256, h: 0.17 },
  chart: { x: 0.185, y: 0.335, w: 0.528, h: 0.435 },
  list: { x: 0.733, y: 0.335, w: 0.252, h: 0.435 },
  bottombar: { x: 0.185, y: 0.805, w: 0.8, h: 0.175 },
}

interface Particle {
  // Orbit (the "swirl" rest state)
  orbitRadius: number
  orbitAngle: number
  orbitSpeed: number
  orbitSquash: number
  wobble: number
  // Assembly target in normalized mockup coords
  tx: number
  ty: number
  size: number
  sprite: number
  alpha: number
}

const COLORS = [
  'rgba(139, 92, 246, 1)', // violet-500 — the accent
  'rgba(167, 139, 250, 1)', // violet-400
  'rgba(226, 232, 240, 1)', // slate-200 (white-ish)
  'rgba(34, 211, 238, 1)', // cyan-400 — sparse
]
// Weighted pick: mostly violet, some white, a little cyan.
const COLOR_WEIGHTS = [0.45, 0.3, 0.2, 0.05]

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/** Sample a point on the EDGE of a rect (the particles trace the UI's skeleton). */
function sampleRectEdge(r: NormRect, rand: () => number): [number, number] {
  const perimeter = 2 * (r.w + r.h)
  let d = rand() * perimeter
  if (d < r.w) return [r.x + d, r.y]
  d -= r.w
  if (d < r.h) return [r.x + r.w, r.y + d]
  d -= r.h
  if (d < r.w) return [r.x + r.w - d, r.y + r.h]
  d -= r.w
  return [r.x, r.y + r.h - d]
}

/** Mulberry32 — deterministic layout across re-mounts, no Math.random flicker. */
function mulberry32(seed: number): () => number {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export class ParticleField {
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  private particles: Particle[] = []
  private sprites: HTMLCanvasElement[] = []
  private progress = 0
  private running = false
  private rafId = 0
  private dpr = 1
  private width = 0
  private height = 0
  /** Mockup bounding box in CSS pixels relative to the canvas. */
  private box = { x: 0, y: 0, w: 0, h: 0 }
  private startTime = performance.now()
  private reducedMotion: boolean

  // Adaptive quality: additive-blended glow over a full viewport is brutal on
  // software rasterizers (VMs, remote panes, old integrated GPUs). The loop
  // measures its own frame time and sheds work until it fits the budget —
  // fewer particles first, then a 1.0 DPR backbuffer. Degrading beats a page
  // that looks great on a good GPU and freezes everywhere else.
  private qualityLevel = 0
  private activeCount = 0
  private frameEma = 16
  private framesSinceCheck = 0
  private lastFrameAt = 0

  constructor(canvas: HTMLCanvasElement, particleCount: number, reducedMotion: boolean) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas 2d unavailable')
    this.ctx = ctx
    this.reducedMotion = reducedMotion
    this.buildSprites()
    this.buildParticles(particleCount)
    this.activeCount = particleCount
  }

  private buildSprites() {
    this.sprites = COLORS.map((color) => {
      const s = document.createElement('canvas')
      s.width = 16
      s.height = 16
      const c = s.getContext('2d')!
      const g = c.createRadialGradient(8, 8, 0, 8, 8, 8)
      g.addColorStop(0, color)
      g.addColorStop(0.4, color.replace(', 1)', ', 0.35)'))
      g.addColorStop(1, color.replace(', 1)', ', 0)'))
      c.fillStyle = g
      c.fillRect(0, 0, 16, 16)
      return s
    })
  }

  private buildParticles(count: number) {
    const rand = mulberry32(0x0b12a1)
    const rects = Object.values(MOCKUP_LAYOUT)
    // Weight target sampling by rect perimeter so big shapes get more particles.
    const perims = rects.map((r) => 2 * (r.w + r.h))
    const totalPerim = perims.reduce((a, b) => a + b, 0)

    this.particles = Array.from({ length: count }, () => {
      // Pick a rect proportionally to its perimeter.
      let pick = rand() * totalPerim
      let ri = 0
      while (pick > perims[ri]) {
        pick -= perims[ri]
        ri++
      }
      const [tx, ty] = sampleRectEdge(rects[ri], rand)

      // Sprite by weight.
      let cw = rand()
      let sprite = 0
      while (cw > COLOR_WEIGHTS[sprite]) {
        cw -= COLOR_WEIGHTS[sprite]
        sprite++
      }

      return {
        orbitRadius: 0.55 + rand() * 0.85, // in units of half-diagonal
        orbitAngle: rand() * Math.PI * 2,
        orbitSpeed: (0.02 + rand() * 0.1) * (rand() > 0.5 ? 1 : -1),
        orbitSquash: 0.45 + rand() * 0.35,
        wobble: rand() * Math.PI * 2,
        tx,
        ty,
        size: 1.6 + rand() * 2.6,
        sprite,
        alpha: 0.35 + rand() * 0.65,
      }
    })
  }

  resize(width: number, height: number, boxPx: { x: number; y: number; w: number; h: number }) {
    // Quality level 2+ drops to a 1.0 DPR backbuffer (quarter the pixels).
    this.dpr = this.qualityLevel >= 2 ? 1 : Math.min(window.devicePixelRatio || 1, 1.5)
    this.width = width
    this.height = height
    this.canvas.width = Math.round(width * this.dpr)
    this.canvas.height = Math.round(height * this.dpr)
    this.canvas.style.width = `${width}px`
    this.canvas.style.height = `${height}px`
    this.box = boxPx
  }

  /** Called from the loop when frames are over budget. Returns true if degraded. */
  private degrade(): boolean {
    if (this.qualityLevel >= 3) return false
    this.qualityLevel++
    this.activeCount = Math.max(350, Math.floor(this.particles.length / 2 ** this.qualityLevel))
    if (this.qualityLevel >= 2) this.resize(this.width, this.height, this.box)
    return true
  }

  setProgress(p: number) {
    this.progress = Math.min(1, Math.max(0, p))
    // Reduced motion renders exactly once per progress change, no loop.
    if (this.reducedMotion) this.renderFrame(0)
  }

  start() {
    if (this.running || this.reducedMotion) {
      if (this.reducedMotion) this.renderFrame(0)
      return
    }
    this.running = true
    this.lastFrameAt = performance.now()
    const loop = () => {
      if (!this.running) return
      const now = performance.now()
      const dt = now - this.lastFrameAt
      this.lastFrameAt = now

      // Exponential moving average of frame time; shed quality when we're
      // consistently blowing a ~30fps budget. A single catastrophic frame
      // (software rasterizer) triggers an immediate drop — nobody should sit
      // through twenty 300ms frames waiting for the average to notice.
      this.frameEma = this.frameEma * 0.85 + Math.min(dt, 400) * 0.15
      this.framesSinceCheck++
      const emergency = dt > 150 && this.framesSinceCheck >= 3
      if (this.framesSinceCheck >= 10 || emergency) {
        this.framesSinceCheck = 0
        if ((this.frameEma > 34 || emergency) && this.degrade()) this.frameEma = 16
      }

      this.renderFrame((now - this.startTime) / 1000)
      this.rafId = requestAnimationFrame(loop)
    }
    this.rafId = requestAnimationFrame(loop)
  }

  stop() {
    this.running = false
    cancelAnimationFrame(this.rafId)
  }

  destroy() {
    this.stop()
    this.particles = []
  }

  private renderFrame(t: number) {
    const { ctx, width, height, box, dpr } = this
    if (width === 0) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)
    ctx.globalCompositeOperation = 'lighter'

    const cx = width / 2
    const cy = height / 2
    const halfDiag = Math.hypot(width, height) / 2
    const p = easeInOutCubic(this.progress)
    // Particles fade out as the crisp DOM dashboard fades in (crossfade window).
    const fadeOut = this.progress > 0.8 ? 1 - (this.progress - 0.8) / 0.2 : 1
    // In reduced motion the field is frozen mid-assembly with no orbit drift.
    const time = this.reducedMotion ? 0 : t

    const count = Math.min(this.activeCount, this.particles.length)
    for (let i = 0; i < count; i++) {
      const pt = this.particles[i]
      const angle = pt.orbitAngle + pt.orbitSpeed * time
      const sx = cx + Math.cos(angle) * pt.orbitRadius * halfDiag
      const sy = cy + Math.sin(angle) * pt.orbitRadius * halfDiag * pt.orbitSquash
      const txPx = box.x + pt.tx * box.w
      const tyPx = box.y + pt.ty * box.h
      // Residual wobble shrinks to zero as the particle locks into place.
      const wob = (1 - p) * 6
      const x = sx + (txPx - sx) * p + Math.sin(time * 1.7 + pt.wobble) * wob
      const y = sy + (tyPx - sy) * p + Math.cos(time * 1.3 + pt.wobble) * wob

      const size = pt.size * (1 + (1 - p) * 0.6)
      ctx.globalAlpha = pt.alpha * fadeOut * (0.5 + 0.5 * p) + pt.alpha * (1 - p) * 0.35
      ctx.drawImage(this.sprites[pt.sprite], x - size * 2, y - size * 2, size * 4, size * 4)
    }
    ctx.globalAlpha = 1
    ctx.globalCompositeOperation = 'source-over'
  }
}
