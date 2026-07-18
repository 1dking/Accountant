/**
 * Cinematic sales page for O-Brain — shown to logged-OUT visitors at `/`.
 *
 * Structure (per the owner's PULSE reference, adapted to the real product):
 * scroll-scrubbed hero where particles assemble a dashboard → integrations
 * strip → three feature reveals pinned over ambient holographic motion →
 * count-up metrics → browser-frame product depiction → pricing with toggle →
 * FAQ accordion → calm final CTA with a demo-request form that posts to the
 * product's own inbound lead webhook.
 *
 * All motion is code-driven (see lib/salesPage/particles.ts for why). The
 * scroll handler writes progress imperatively to the canvas and to CSS custom
 * properties — React never re-renders on scroll except when the pinned trio
 * crosses a segment boundary.
 *
 * Honesty rules baked in: counters state product facts, the logo strip lists
 * real integrations (not invented customers), pricing shows the seeded tier
 * numbers, and annual pricing says "talk to us" because the seeded annual
 * values are incoherent (flagged to the owner) — we don't invent prices.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { MOCKUP_LAYOUT, ParticleField } from '@/lib/salesPage/particles'
import { useCountUp } from '@/lib/salesPage/useCountUp'
import { DEMO_WEBHOOK_KEY } from '@/lib/salesPage/config'
import './sales-page.css'

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function smoothstep(a: number, b: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

/** Progress 0→1 of a tall scrub section as it passes through the viewport. */
function sectionProgress(el: HTMLElement): number {
  const rect = el.getBoundingClientRect()
  const track = rect.height - window.innerHeight
  if (track <= 0) return 0
  return Math.min(1, Math.max(0, -rect.top / track))
}

const pct = (n: number) => `${n * 100}%`
const rectStyle = (key: keyof typeof MOCKUP_LAYOUT) => {
  const r = MOCKUP_LAYOUT[key]
  return { left: pct(r.x), top: pct(r.y), width: pct(r.w), height: pct(r.h) }
}

// Deterministic streaming-digit columns for the ambient layer.
const DIGIT_COLUMN = Array.from({ length: 60 }, (_, i) =>
  String((i * 7919 + 104729) % 100_000).padStart(5, '0'),
).join('\n')

// ---------------------------------------------------------------------------
// the dashboard mockup (shared: hero assembly target + browser-frame section)
// ---------------------------------------------------------------------------

function DashboardMockup({ innerRef }: { innerRef?: (el: HTMLDivElement | null) => void }) {
  return (
    <div className="sp-mockup" ref={innerRef} aria-hidden="true">
      <div className="sp-mock-panel" style={rectStyle('sidebar')}>
        <p className="sp-mock-label">O-Brain</p>
        <div className="sp-mock-navdot active" />
        <div className="sp-mock-navdot" />
        <div className="sp-mock-navdot" />
        <div className="sp-mock-navdot" />
        <div className="sp-mock-navdot" />
      </div>
      <div className="sp-mock-panel" style={rectStyle('topbar')}>
        <div className="sp-mock-row short" style={{ marginTop: '0.35rem' }} />
      </div>
      <div className="sp-mock-panel" style={rectStyle('card1')}>
        <p className="sp-mock-label">Outstanding</p>
        <p className="sp-mock-value">$12,480</p>
      </div>
      <div className="sp-mock-panel" style={rectStyle('card2')}>
        <p className="sp-mock-label">Collected this month</p>
        <p className="sp-mock-value accent">$8,920</p>
      </div>
      <div className="sp-mock-panel" style={rectStyle('card3')}>
        <p className="sp-mock-label">Meetings today</p>
        <p className="sp-mock-value">4</p>
      </div>
      <div className="sp-mock-panel" style={rectStyle('chart')}>
        <p className="sp-mock-label">Cash in</p>
        <svg className="sp-mock-chart-svg" viewBox="0 0 100 40" preserveAspectRatio="none">
          <defs>
            <linearGradient id="spChartGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(139,92,246,0.55)" />
              <stop offset="100%" stopColor="rgba(139,92,246,0)" />
            </linearGradient>
          </defs>
          <polygon
            className="sp-chart-fill"
            points="0,36 8,32 14,33 20,28 24,29 30,24 34,8 38,30 44,26 50,22 56,23 62,16 68,18 74,10 82,12 90,4 100,6 100,40 0,40"
          />
          <polyline
            className="sp-chart-line"
            pathLength={1}
            points="0,36 8,32 14,33 20,28 24,29 30,24 34,8 38,30 44,26 50,22 56,23 62,16 68,18 74,10 82,12 90,4 100,6"
          />
          <circle className="sp-chart-dot" cx="100" cy="6" r="4" />
        </svg>
      </div>
      <div className="sp-mock-panel" style={rectStyle('list')}>
        <p className="sp-mock-label">Today</p>
        <div className="sp-mock-row" />
        <div className="sp-mock-row short" />
        <div className="sp-mock-row" />
        <div className="sp-mock-row short" />
      </div>
      <div className="sp-mock-panel" style={rectStyle('bottombar')}>
        <div className="sp-mock-row" style={{ width: '40%', display: 'inline-block', marginRight: '4%' }} />
        <div className="sp-mock-row" style={{ width: '26%', display: 'inline-block' }} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ambient holographic layer for the pinned trio
// ---------------------------------------------------------------------------

function Sparkline({ points, anomaly }: { points: string; anomaly?: { x: number; y: number } }) {
  return (
    <svg viewBox="0 0 100 36" width="100%" height="52" preserveAspectRatio="none">
      <polyline points={points} />
      {anomaly && (
        <>
          <circle className="sp-anomaly" cx={anomaly.x} cy={anomaly.y} r="3" />
          <circle className="sp-anomaly-ring" cx={anomaly.x} cy={anomaly.y} r="9" />
        </>
      )}
    </svg>
  )
}

const HOLO_CARDS = [
  { style: { top: '12%', left: '7%', width: 'min(240px, 26vw)', '--tilt': '-3deg' }, points: '0,28 14,24 28,26 42,18 56,20 70,12 84,14 100,6' },
  {
    style: { top: '18%', right: '9%', width: 'min(280px, 30vw)', '--tilt': '2.5deg', animationDelay: '-4s' },
    points: '0,20 12,22 26,16 40,19 52,10 64,24 78,8 100,12',
    anomaly: { x: 64, y: 24 },
  },
  { style: { bottom: '16%', left: '12%', width: 'min(260px, 28vw)', '--tilt': '2deg', animationDelay: '-7s' }, points: '0,30 16,28 30,22 44,25 60,15 76,17 100,8' },
  { style: { bottom: '11%', right: '14%', width: 'min(210px, 24vw)', '--tilt': '-2deg', animationDelay: '-2s' }, points: '0,18 15,14 30,20 45,10 60,13 78,6 100,10' },
] as const

const REVEALS = [
  { word: 'Capture', line: 'Every call, email and receipt files itself — scanned, transcribed and remembered.' },
  { word: 'Automate', line: 'Follow-ups, invoices and replies run on triggers while you do the actual work.' },
  { word: 'Collect', line: 'Proposals get signed. Invoices get paid. The money side runs itself.' },
] as const

// ---------------------------------------------------------------------------
// sections
// ---------------------------------------------------------------------------

const INTEGRATIONS = ['Stripe', 'Twilio', 'Gmail', 'Google Calendar', 'Plaid', 'LiveKit', 'AssemblyAI']

/**
 * Real screenshots of the product (webp'd from a seeded demo workspace) shown
 * in the 3D showcase. The backdrop is AI-generated atmosphere; the screenshots
 * are genuine pixels — AI re-rendering garbles UI text, so we composite the
 * real thing over the glow instead of letting a model repaint it.
 */
const FEATURE_SHOTS = [
  { key: 'dashboard', label: 'Dashboard', category: 'Overview', src: '/showcase/dashboard.webp', line: 'Your whole business at a glance — revenue, outstanding, meetings, approvals.' },
  { key: 'contacts', label: 'Contacts', category: 'CRM & sales', src: '/showcase/contacts.webp', line: 'Private per-employee books, shared only when you explicitly say so.' },
  { key: 'pipeline', label: 'Pipeline', category: 'CRM & sales', src: '/showcase/pipeline.webp', line: 'Every deal staged from draft to won, totals per stage.' },
  { key: 'proposals', label: 'Proposals', category: 'CRM & sales', src: '/showcase/proposals.webp', line: 'E-signature proposals that turn into invoices the moment they are won.' },
  { key: 'cashbook', label: 'Cashbook', category: 'Accounting', src: '/showcase/cashbook.webp', line: 'Every dollar in and out, with reconciliation against real bank feeds.' },
  { key: 'reports', label: 'Reports', category: 'Accounting', src: '/showcase/reports.webp', line: 'P&L, cash flow, tax and aging — always current, exportable.' },
  { key: 'phone', label: 'Phone', category: 'Communication', src: '/showcase/phone.webp', line: 'Browser calling, voicemail transcripts, and a dial queue — no separate phone system.' },
  { key: 'inbox', label: 'Inbox', category: 'Communication', src: '/showcase/inbox.webp', line: 'Every email and text thread in one unified inbox.' },
  { key: 'meetings', label: 'Meetings', category: 'Meetings', src: '/showcase/meetings.webp', line: 'Video rooms with AI transcription, summaries and action items.' },
  { key: 'page-builder', label: 'Website', category: 'Content', src: '/showcase/page-builder.webp', line: 'AI-generated pages, published on a custom domain, with real analytics.' },
  { key: 'forms', label: 'Forms', category: 'Content', src: '/showcase/forms.webp', line: 'Embeddable forms plus an inbound webhook — leads from your site land straight in the CRM.' },
  { key: 'workflows', label: 'Workflows', category: 'Automation', src: '/showcase/workflows.webp', line: '20+ triggers wired to real email, SMS, tag and webhook actions.' },
] as const

/**
 * The hybrid 3D feature showcase: a Higgsfield-generated ambient backdrop with
 * the REAL screenshots in a CSS-3D-tilted glass frame over it. Mouse movement
 * tilts the frame (written to CSS vars imperatively — no re-render per move);
 * reduced motion pins it flat.
 */
function FeatureShowcase() {
  const [active, setActive] = useState(0)
  const stageRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef(0)

  const onMove = useCallback((e: React.MouseEvent) => {
    const stage = stageRef.current
    if (!stage || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const rect = stage.getBoundingClientRect()
    const nx = (e.clientX - rect.left) / rect.width - 0.5
    const ny = (e.clientY - rect.top) / rect.height - 0.5
    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      stage.style.setProperty('--tilt-y', `${(nx * 7).toFixed(2)}deg`)
      stage.style.setProperty('--tilt-x', `${(-ny * 5).toFixed(2)}deg`)
    })
  }, [])

  const onLeave = useCallback(() => {
    const stage = stageRef.current
    if (!stage) return
    cancelAnimationFrame(rafRef.current)
    stage.style.setProperty('--tilt-y', '0deg')
    stage.style.setProperty('--tilt-x', '0deg')
  }, [])

  useEffect(() => () => cancelAnimationFrame(rafRef.current), [])

  return (
    <div className="sp-showcase-stage" ref={stageRef} onMouseMove={onMove} onMouseLeave={onLeave}>
      <div className="sp-showcase-frame">
        {FEATURE_SHOTS.map((shot, i) => (
          <img
            key={shot.key}
            src={shot.src}
            alt={`${shot.label} — real product screenshot`}
            loading={i === 0 ? 'eager' : 'lazy'}
            className={active === i ? 'active' : ''}
          />
        ))}
        <div className="sp-showcase-shine" />
      </div>
      <p className="sp-showcase-category">{FEATURE_SHOTS[active].category}</p>
      <p className="sp-showcase-line">{FEATURE_SHOTS[active].line}</p>
      <div className="sp-showcase-tabs" role="tablist" aria-label="Feature screenshots">
        {FEATURE_SHOTS.map((shot, i) => (
          <button
            key={shot.key}
            role="tab"
            aria-selected={active === i}
            className={active === i ? 'on' : ''}
            onClick={() => setActive(i)}
          >
            {shot.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Counter({ target, suffix, label }: { target: number; suffix: string; label: string }) {
  const { ref, value } = useCountUp(target)
  return (
    <div className="sp-counter">
      <div className="sp-counter-num" ref={ref as React.RefObject<HTMLDivElement>}>
        {value}
        {suffix}
      </div>
      <div className="sp-counter-label">{label}</div>
    </div>
  )
}

interface Plan {
  name: string
  monthly: string
  featured?: boolean
  bullets: string[]
}

// Real seeded platform tiers (platform_admin DEFAULT_PRICING_SETTINGS).
const PLANS: Plan[] = [
  {
    name: 'Starter',
    monthly: '$0',
    bullets: ['CRM, invoicing & meetings included', '3 published pages', '1 GB drive storage', '50 AI messages / month'],
  },
  {
    name: 'Pro',
    monthly: '$29',
    featured: true,
    bullets: ['Everything in Starter', '25 published pages', '10 GB drive storage', '500 AI messages / month'],
  },
  {
    name: 'Business',
    monthly: '$79',
    bullets: ['Everything in Pro', '100 published pages', '50 GB drive storage', 'For teams running everything here'],
  },
]

const FAQS = [
  {
    q: 'What do I actually get?',
    a: 'One login for the whole business: CRM, invoices and estimates, e-signature proposals, a cashbook with real financial reports, video meetings with AI notes, a browser phone with SMS, collaborative docs, sheets and slides, cloud drive, and an automation engine tying it together. Plans differ by published pages, storage and AI message quotas — not by locking away features.',
  },
  {
    q: 'Can I control what each employee sees?',
    a: 'Yes, on two axes. Every employee gets their own private book — two people making calls never see each other’s contacts, and managers see only their own team. Separately, you toggle which modules each person can open: the accountant gets the cashbook and invoicing, a VA gets just the dialer. Both are enforced on the server, not just hidden in the menu.',
  },
  {
    q: 'Does it work with the tools I already use?',
    a: 'Payments run through Stripe (Pay Now links on every invoice). Calls and SMS run on Twilio. Gmail scanning auto-files emailed invoices. Google Calendar two-way syncs your bookings. Plaid pulls bank transactions for one-click reconciliation. Meetings run on LiveKit with AssemblyAI transcription.',
  },
  {
    q: 'How does the AI part work?',
    a: 'O-Brain chats with the full context of your business and can draft and send email or SMS — always with your confirmation first. Meetings are transcribed and summarised into action items, and can even produce a draft quote from what was discussed. The monthly Coach report analyses your win/loss patterns and scores your business health 1–100.',
  },
  {
    q: 'Can it look like my company instead of yours?',
    a: 'The white-label add-on covers logos (light and dark), brand colors and fonts, email header and footer, the client portal, public booking pages and custom domains for anything you publish.',
  },
  {
    q: 'What happens when someone leaves my team?',
    a: 'An admin transfers their entire book — contacts and every attached invoice, proposal, call and task — to whoever takes over, in one action. Nothing is lost with the seat.',
  },
  {
    q: 'How do I start?',
    a: 'Book a demo below and we’ll set your workspace up — the Starter tier is genuinely $0. If your team already uses it, just log in.',
  },
]

// ---------------------------------------------------------------------------
// the page
// ---------------------------------------------------------------------------

export default function SalesPage() {
  const [navScrolled, setNavScrolled] = useState(false)
  const [trioSegment, setTrioSegment] = useState(0)
  const [annual, setAnnual] = useState(false)
  const [openFaq, setOpenFaq] = useState<number | null>(0)

  const heroRef = useRef<HTMLElement | null>(null)
  const heroStickyRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const mockupRef = useRef<HTMLDivElement | null>(null)
  const trioRef = useRef<HTMLElement | null>(null)
  const fieldRef = useRef<ParticleField | null>(null)
  const trioSegmentRef = useRef(0)
  const navScrolledRef = useRef(false)

  // Build the particle field + wire the scrub. Everything imperative.
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const hero = heroRef.current
    const sticky = heroStickyRef.current
    const canvas = canvasRef.current
    const mockup = mockupRef.current
    const trio = trioRef.current
    if (!hero || !sticky || !canvas || !mockup || !trio) return

    let field: ParticleField | null = null
    if (!reduced) {
      const count = window.innerWidth < 720 ? 1200 : 2600
      field = new ParticleField(canvas, count, reduced)
      fieldRef.current = field
    }

    const measure = () => {
      if (!field) return
      const s = sticky.getBoundingClientRect()
      const m = mockup.getBoundingClientRect()
      field.resize(s.width, s.height, {
        x: m.left - s.left,
        y: m.top - s.top,
        w: m.width,
        h: m.height,
      })
    }
    measure()

    const onScroll = () => {
      // Nav chrome
      const scrolled = window.scrollY > 24
      if (scrolled !== navScrolledRef.current) {
        navScrolledRef.current = scrolled
        setNavScrolled(scrolled)
      }

      // Hero scrub → canvas + CSS vars (no React involved)
      const p = sectionProgress(hero)
      field?.setProgress(p)
      hero.style.setProperty('--hero-p', p.toFixed(4))
      hero.style.setProperty('--mock-o', smoothstep(0.55, 0.9, p).toFixed(4))
      hero.style.setProperty('--copy-shift', smoothstep(0.22, 0.7, p).toFixed(4))
      hero.style.setProperty('--chart-draw', smoothstep(0.66, 0.96, p).toFixed(4))

      // Trio segment (state change only at boundaries)
      const tp = sectionProgress(trio)
      const seg = tp < 1 / 3 ? 0 : tp < 2 / 3 ? 1 : 2
      if (seg !== trioSegmentRef.current) {
        trioSegmentRef.current = seg
        setTrioSegment(seg)
      }
    }

    // Run the particle loop only while the hero is on screen.
    const heroVisible = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) field?.start()
        else field?.stop()
      },
      { threshold: 0 },
    )
    heroVisible.observe(hero)

    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', measure)
    onScroll()

    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', measure)
      heroVisible.disconnect()
      field?.destroy()
      fieldRef.current = null
    }
  }, [])

  const scrollToDemo = useCallback(() => {
    document.getElementById('sp-demo')?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Demo-request form → the product's own inbound lead webhook.
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' })
  const [formState, setFormState] = useState<'idle' | 'sending' | 'ok' | 'error'>('idle')

  const submitDemo = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!DEMO_WEBHOOK_KEY) return
    setFormState('sending')
    try {
      const resp = await fetch(`/api/forms/webhook/${DEMO_WEBHOOK_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, source: 'sales-page' }),
      })
      setFormState(resp.ok ? 'ok' : 'error')
    } catch {
      setFormState('error')
    }
  }

  return (
    <div className="sp-root">
      {/* nav */}
      <nav className={`sp-nav${navScrolled ? ' scrolled' : ''}`}>
        <a className="sp-logo" href="/">
          O<span className="dot">·</span>Brain
        </a>
        <div className="sp-nav-links">
          <a className="sp-nav-anchor" href="#sp-features">Features</a>
          <a className="sp-nav-anchor" href="#sp-pricing">Pricing</a>
          <a className="sp-nav-anchor" href="#sp-faq">FAQ</a>
          <Link to="/login" className="sp-btn sp-btn-ghost sp-btn-small">
            Log in
          </Link>
          <button className="sp-btn sp-btn-primary sp-btn-small" onClick={scrollToDemo}>
            Get started free
          </button>
        </div>
      </nav>

      {/* HERO — particles assemble the dashboard as you scroll */}
      <section className="sp-hero" ref={heroRef}>
        <div className="sp-hero-sticky" ref={heroStickyRef}>
          <canvas className="sp-hero-canvas" ref={canvasRef} aria-hidden="true" />
          <DashboardMockup innerRef={(el) => (mockupRef.current = el)} />
          <div className="sp-hero-copy">
            <h1 className="sp-hero-h1">
              Your business,
              <br />
              remembered.
            </h1>
            <p className="sp-hero-sub">
              CRM, invoicing, meetings, phone and an AI that never forgets a call, a receipt or a
              follow-up — one login for the whole company.
            </p>
            <div className="sp-hero-cta">
              <button className="sp-btn sp-btn-primary" onClick={scrollToDemo}>
                Get started free
              </button>
              <Link to="/login" className="sp-btn sp-btn-ghost">
                Log in
              </Link>
            </div>
          </div>
          <div className="sp-scroll-hint">Scroll</div>
        </div>
      </section>

      {/* integrations strip — real integrations, not invented customers */}
      <section className="sp-integrations">
        <p>Runs on the tools you already trust</p>
        <div className="sp-logo-row">
          {INTEGRATIONS.map((name) => (
            <span key={name}>{name}</span>
          ))}
        </div>
      </section>

      {/* pinned trio over ambient holographic motion */}
      <section className="sp-trio" id="sp-features" ref={trioRef}>
        <div className="sp-trio-sticky">
          <div className="sp-digits" style={{ left: '4%' }} aria-hidden="true">
            {DIGIT_COLUMN}
          </div>
          <div className="sp-digits" style={{ right: '6%', animationDelay: '-12s' }} aria-hidden="true">
            {DIGIT_COLUMN}
          </div>
          {HOLO_CARDS.map((card, i) => (
            <div key={i} className="sp-holo" style={card.style as React.CSSProperties} aria-hidden="true">
              <Sparkline points={card.points} anomaly={'anomaly' in card ? card.anomaly : undefined} />
            </div>
          ))}
          {REVEALS.map((r, i) => (
            <div key={r.word} className={`sp-reveal${trioSegment === i ? ' active' : ''}`}>
              <h2 className="sp-reveal-word">
                <em>{r.word}</em>
              </h2>
              <p className="sp-reveal-line">{r.line}</p>
            </div>
          ))}
          <div className="sp-trio-dots" aria-hidden="true">
            {REVEALS.map((_, i) => (
              <i key={i} className={trioSegment === i ? 'on' : ''} />
            ))}
          </div>
        </div>
      </section>

      <div className="sp-fade-to-light" />

      <div className="sp-light">
        {/* counters — product facts, not invented social proof */}
        <section className="sp-section">
          <p className="sp-kicker">Everything, in one place</p>
          <h2 className="sp-h2">Stop paying for ten tools that don&apos;t talk to each other.</h2>
          <p className="sp-body-sub">
            Every module shares one memory: the receipt you photographed shows up on the contact, the
            meeting summary becomes the quote, the signed proposal becomes the invoice.
          </p>
          <div className="sp-counters">
            <Counter target={25} suffix="+" label="built-in tools behind one login" />
            <Counter target={20} suffix="+" label="automation triggers doing your follow-up" />
            <Counter target={24} suffix="/7" label="background automation, always on" />
          </div>
        </section>

        {/* the real product, floating in the glow — genuine screenshots, not a mockup */}
        <section className="sp-showcase">
          <div className="sp-section">
            <p className="sp-kicker">The real thing</p>
            <h2 className="sp-h2">Open one tab. Know everything.</h2>
            <p className="sp-body-sub" style={{ margin: '0 auto' }}>
              Live screenshots from a working O-Brain workspace — not concept art.
            </p>
            <FeatureShowcase />
          </div>
        </section>

        {/* pricing */}
        <section className="sp-section" id="sp-pricing" style={{ textAlign: 'center' }}>
          <p className="sp-kicker">Pricing</p>
          <h2 className="sp-h2">Start free. Grow when you do.</h2>
          <div className="sp-toggle" role="group" aria-label="Billing period">
            <button className={annual ? '' : 'on'} onClick={() => setAnnual(false)}>
              Monthly
            </button>
            <button className={annual ? 'on' : ''} onClick={() => setAnnual(true)}>
              Annual
            </button>
          </div>
          <div className="sp-plans">
            {PLANS.map((plan) => (
              <div key={plan.name} className={`sp-plan${plan.featured ? ' featured' : ''}`}>
                {plan.featured && <span className="sp-plan-flag">Most popular</span>}
                <h3>{plan.name}</h3>
                {annual && plan.monthly !== '$0' ? (
                  <div className="sp-plan-talk">Talk to us</div>
                ) : (
                  <div className="sp-plan-price">
                    {plan.monthly}
                    <small> /month</small>
                  </div>
                )}
                <ul style={{ textAlign: 'left' }}>
                  {plan.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
                <button
                  className={`sp-btn ${plan.featured ? 'sp-btn-primary' : 'sp-btn-ghost'}`}
                  style={plan.featured ? undefined : { color: 'var(--sp-body-text)', borderColor: '#ddd9ee' }}
                  onClick={scrollToDemo}
                >
                  {plan.monthly === '$0' ? 'Start free' : 'Book a demo'}
                </button>
              </div>
            ))}
          </div>
          <p className="sp-plan-note">
            Enterprise from $199/month · Add-ons: SMS $15 · custom domain $9 · white-label $49 ·
            unlimited AI messages $19 · O-Brain AI tiers from $49/month
          </p>
        </section>

        {/* FAQ */}
        <section className="sp-section" id="sp-faq">
          <p className="sp-kicker">Questions</p>
          <h2 className="sp-h2">Fair questions, straight answers.</h2>
          <div className="sp-faq">
            {FAQS.map((f, i) => (
              <div key={f.q} className={`sp-faq-item${openFaq === i ? ' open' : ''}`}>
                <button
                  className="sp-faq-q"
                  aria-expanded={openFaq === i}
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                >
                  {f.q}
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
                <div className="sp-faq-a">
                  <div>
                    <p>{f.a}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* final CTA — the calm */}
      <section className="sp-calm" id="sp-demo">
        <div className="sp-wisp" style={{ top: '8%', left: '12%' }} />
        <div className="sp-wisp" style={{ bottom: '4%', right: '10%', animationDelay: '-8s' }} />
        <div className="sp-section">
          <p className="sp-kicker">Everything under control</p>
          <h2 className="sp-h2">Run tomorrow with a clear head.</h2>
          <p className="sp-body-sub" style={{ margin: '0 auto' }}>
            Tell us where to reach you and we&apos;ll set your workspace up — the Starter tier is
            genuinely free.
          </p>
          {DEMO_WEBHOOK_KEY ? (
            formState === 'ok' ? (
              <p className="sp-form-ok">
                Got it — your request just became a contact in our own CRM. We&apos;ll be in touch shortly.
              </p>
            ) : (
              <form className="sp-demo-form" onSubmit={submitDemo}>
                <input
                  required
                  placeholder="Your name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
                <input
                  required
                  type="email"
                  placeholder="Work email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
                <input
                  placeholder="Company (optional)"
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                />
                <textarea
                  rows={3}
                  placeholder="What should we show you first? (optional)"
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                />
                <button className="sp-btn sp-btn-primary" disabled={formState === 'sending'} type="submit">
                  {formState === 'sending' ? 'Sending…' : 'Get started free'}
                </button>
                {formState === 'error' && (
                  <p style={{ color: '#be123c', fontSize: '0.85rem', margin: 0 }}>
                    That didn&apos;t go through — try again, or email us directly.
                  </p>
                )}
              </form>
            )
          ) : (
            <div className="sp-hero-cta" style={{ marginTop: '2rem' }}>
              <Link to="/login" className="sp-btn sp-btn-primary">
                Log in to your workspace
              </Link>
            </div>
          )}
        </div>
      </section>

      <footer className="sp-footer">
        <div>
          <Link to="/login">Log in</Link>
          <Link to="/portal">Client portal</Link>
          <a href="#sp-pricing">Pricing</a>
        </div>
        <p style={{ marginTop: '0.9rem' }}>O-Brain — Your business, remembered. · An OCIDM product</p>
      </footer>
    </div>
  )
}
