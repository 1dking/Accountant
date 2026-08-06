/**
 * Dedicated Features page (public, `/features`).
 *
 * The sales-page showcase is a tabbed teaser — one line per feature. This page
 * gives every module its own screenshot and a proper block of copy: what it is,
 * what it does, and why it earns its place. Grouped by area, alternating
 * image/text rows. Screenshots are the same real product shots served from
 * /showcase (seeded demo workspace — no real client or financial data).
 *
 * Scoped under .fp-root so the app's brand theme vars can't bleed in.
 */
import { useEffect } from 'react'
import { Link } from 'react-router'
import './features-page.css'

interface Feature {
  key: string
  group: string
  name: string
  tagline: string
  body: string
  points: string[]
}

const FEATURES: Feature[] = [
  // ---- Overview ----
  {
    key: 'dashboard',
    group: 'Overview',
    name: 'Dashboard',
    tagline: 'Your whole business on one screen.',
    body: 'The moment you log in, O-Brain surfaces what actually needs you: revenue this month, what’s still outstanding, the meetings on today’s calendar, and anything waiting on your approval. Every number is live and clicks straight through to the detail behind it.',
    points: ['Revenue, outstanding and cash trends at a glance', 'Today’s meetings and upcoming deadlines', 'Pending approvals and unread messages surfaced'],
  },

  // ---- CRM & sales ----
  {
    key: 'contacts',
    group: 'CRM & sales',
    name: 'Contacts',
    tagline: 'A CRM that remembers every conversation.',
    body: 'Each contact carries a full timeline — calls, emails, texts, invoices, proposals and notes — so you never open a conversation cold. Books are private per employee by default: two people making calls never see each other’s contacts, and you share a record only when you choose to.',
    points: ['Complete interaction history per contact', 'Private per-employee books, shared on demand', 'An AI-written brief before any call'],
  },
  {
    key: 'pipeline',
    group: 'CRM & sales',
    name: 'Pipeline',
    tagline: 'Every deal, staged from first touch to won.',
    body: 'Drag deals through your stages and watch the totals update per column, so you always know what’s in play and what’s about to close. A won deal flows straight into a proposal or invoice — nothing gets re-typed.',
    points: ['Stage-by-stage totals', 'Drag-and-drop deal management', 'One click from won to proposal or invoice'],
  },
  {
    key: 'proposals',
    group: 'CRM & sales',
    name: 'Proposals',
    tagline: 'E-signature proposals that become invoices when won.',
    body: 'Send a branded, itemized proposal your client signs in the browser. The moment it’s accepted it turns into an invoice with a Pay Now button — the whole close-to-cash step happens without you touching a second tool.',
    points: ['Legally-binding e-signature', 'Auto-converts to an invoice on acceptance', 'Track opened, signed and paid'],
  },
  {
    key: 'estimates',
    group: 'CRM & sales',
    name: 'Estimates',
    tagline: 'Quotes that convert in a single click.',
    body: 'Build a quote, send it, and turn it into an invoice the instant the client says yes. Line items, taxes and totals carry over exactly, so nothing is re-keyed or lost between the yes and the bill.',
    points: ['Reusable line items', 'One-click convert to invoice', 'Accept and decline tracking'],
  },
  {
    key: 'invoices',
    group: 'CRM & sales',
    name: 'Invoices',
    tagline: 'Get paid faster, chase less.',
    body: 'Every invoice is a clean PDF with a Stripe “Pay Now” button, so clients pay by card in seconds. O-Brain handles partial payments, sends reminders on its own, and flags anything overdue before it becomes a problem.',
    points: ['Stripe Pay Now on every invoice', 'Automatic payment reminders', 'Partial payments and overdue detection'],
  },

  // ---- Accounting ----
  {
    key: 'cashbook',
    group: 'Accounting',
    name: 'Cashbook',
    tagline: 'Every dollar in and out — personal and business kept apart.',
    body: 'The cashbook is the heart of your books: every transaction, categorized and reconciled against the real bank balance. Because one account is often used for both, you can tag any transaction as personal or business — personal items book as owner’s draw, so they stay in your reconciliation but never touch your business P&L or tax.',
    points: ['One ledger, reconciled to the bank', 'Personal vs business tagging from a shared feed', 'Owner’s-draw handling keeps your tax clean'],
  },
  {
    key: 'reconcile',
    group: 'Accounting',
    name: 'Reconcile',
    tagline: 'Prove your books match the bank.',
    body: 'Reconciliation puts your recorded balance next to the bank’s actual balance and shows exactly where — and by how much — they drift. Match transactions, clear the difference, and close the period knowing the numbers are real.',
    points: ['Book vs bank balance, side by side', 'Instant drift detection', 'Match, clear and lock a period'],
  },
  {
    key: 'bank-feeds',
    group: 'Accounting',
    name: 'Bank feeds',
    tagline: 'Live transactions, straight from the bank.',
    body: 'Connect your accounts through Plaid and O-Brain pulls transactions automatically, ready to categorize. No CSV exports, no manual entry — the feed simply stays current, and saved rules do the sorting.',
    points: ['Secure bank connection via Plaid', 'Auto-syncing transactions', 'Bulk categorize with saved rules'],
  },
  {
    key: 'email-scanner',
    group: 'Accounting',
    name: 'Email scanner',
    tagline: 'Invoices and receipts, read out of your inbox.',
    body: 'Point O-Brain at Gmail and it finds the invoices and receipts hiding in your email, reads the amount, vendor and date, and files them into your books as expense or income. The paperwork you’d normally forget gets captured on its own.',
    points: ['Scans Gmail for invoices and receipts', 'Extracts amount, vendor and tax', 'Files as expense or income — business or personal'],
  },
  {
    key: 'receipt-capture',
    group: 'Accounting',
    name: 'Receipts',
    tagline: 'Snap it and forget it.',
    body: 'Photograph a receipt and O-Brain reads the total, vendor and tax, then attaches it to the right transaction. Come tax time, every claim already has its proof stapled to it — no shoebox, no scramble.',
    points: ['Photo to structured data', 'Auto-attached to the transaction', 'Audit-ready record keeping'],
  },
  {
    key: 'smart-import',
    group: 'Accounting',
    name: 'Smart import',
    tagline: 'Drop in a statement, get a clean ledger.',
    body: 'Upload a CSV or PDF bank statement and O-Brain maps every row — date, description, amount, direction — into your cashbook, learning your categories as it goes. Months of backlog become a few minutes of review.',
    points: ['CSV and PDF statements', 'AI column mapping', 'Learns your categorization'],
  },
  {
    key: 'expenses',
    group: 'Accounting',
    name: 'Expenses',
    tagline: 'Spending you can actually control.',
    body: 'Track categorized expenses with receipts attached and approval flows for anything that needs a sign-off. You see where the money is going, and nothing gets paid without the right eyes on it first.',
    points: ['Categorized spending with receipts', 'Approval workflows', 'Vendor and category breakdowns'],
  },
  {
    key: 'income',
    group: 'Accounting',
    name: 'Income',
    tagline: 'Every payment tied to where it came from.',
    body: 'Record income against the client and the invoice it settles, so revenue always traces back to a source. Reconciliation and reporting stay honest because nothing is left floating, unattributed.',
    points: ['Payments linked to client and invoice', 'Clean revenue attribution', 'Feeds your P&L automatically'],
  },
  {
    key: 'recurring',
    group: 'Accounting',
    name: 'Recurring',
    tagline: 'Set the regulars once.',
    body: 'Rent, software, retainers and anything else that repeats gets posted on schedule, automatically. Your books stay complete without you remembering to enter the same thing every month.',
    points: ['Scheduled recurring entries', 'Income or expense', 'Never miss a regular'],
  },
  {
    key: 'budgets',
    group: 'Accounting',
    name: 'Budgets',
    tagline: 'A plan you can watch in real time.',
    body: 'Set a budget per category and O-Brain tracks actuals against it as money moves — so overspend is visible while you can still do something about it, not at year-end when it’s too late.',
    points: ['Per-category budgets', 'Live actual-vs-plan', 'Early overspend warning'],
  },
  {
    key: 'reports',
    group: 'Accounting',
    name: 'Reports',
    tagline: 'The statements your accountant asks for, always current.',
    body: 'P&L, balance sheet, cash flow, sales-tax and aging reports generate from your live data — there’s no month-end scramble to assemble them. Export any of them for your accountant or the tax authority in a click.',
    points: ['P&L, balance sheet and cash flow', 'Sales tax (GST/HST) and aging', 'Export-ready any time'],
  },

  // ---- Communication ----
  {
    key: 'inbox',
    group: 'Communication',
    name: 'Inbox',
    tagline: 'Every conversation in one thread.',
    body: 'Email and SMS land in a single unified inbox, threaded by contact, so you’re not switching apps to follow a conversation. Reply from here and it’s logged against the contact automatically.',
    points: ['Email and SMS unified', 'Threaded by contact', 'Replies logged to the CRM'],
  },
  {
    key: 'phone',
    group: 'Communication',
    name: 'Phone',
    tagline: 'A phone system built into your browser.',
    body: 'Make and take calls right inside O-Brain — no desk phone, no separate app. Voicemails are transcribed, calls are logged to the contact, and a dial queue keeps your outbound calling moving.',
    points: ['Browser calling on Twilio', 'Voicemail transcription', 'Call logging and a dial queue'],
  },

  // ---- Meetings & scheduling ----
  {
    key: 'meetings',
    group: 'Meetings & scheduling',
    name: 'Meetings',
    tagline: 'Video calls that take their own notes.',
    body: 'Run video meetings in the browser with AI transcription in the background. Afterward you get a summary and action items — and O-Brain can even turn what was discussed into a draft quote before you’ve left the call.',
    points: ['Browser video rooms on LiveKit', 'AI transcript, summary and action items', 'Draft a quote from the conversation'],
  },
  {
    key: 'calendar',
    group: 'Meetings & scheduling',
    name: 'Calendar',
    tagline: 'One calendar, synced both ways with Google.',
    body: 'Your bookings and events live in O-Brain and sync two-way with Google Calendar, so whatever you or your client changes shows up on both sides. No double-booking, no copy-paste between tools.',
    points: ['Two-way Google Calendar sync', 'Bookings and events in one place', 'No double-booking'],
  },
  {
    key: 'scheduling',
    group: 'Meetings & scheduling',
    name: 'Scheduling',
    tagline: 'Let clients book you without the back-and-forth.',
    body: 'Share a booking page and clients pick a slot that drops straight into your calendar. Availability, buffers, confirmations and reminders are handled for you.',
    points: ['Shareable booking pages', 'Auto confirmations and reminders', 'Feeds your synced calendar'],
  },

  // ---- Docs & content ----
  {
    key: 'docs',
    group: 'Docs & content',
    name: 'Docs',
    tagline: 'Real-time documents, no Google account needed.',
    body: 'Write and collaborate on documents with live cursors and instant saving, right inside your workspace. Share with a client by link without either of you signing into anything else.',
    points: ['Live multi-user editing', 'Autosave and version history', 'Share by link'],
  },
  {
    key: 'sheets',
    group: 'Docs & content',
    name: 'Sheets',
    tagline: 'Spreadsheets that live with your data.',
    body: 'Build spreadsheets with formulas, shared and edited in real time by your team. Keep your working numbers in the same place as everything they connect to.',
    points: ['Formulas and live collaboration', 'Shared in your workspace', 'No extra login'],
  },
  {
    key: 'slides',
    group: 'Docs & content',
    name: 'Slides',
    tagline: 'Decks without leaving the workspace.',
    body: 'Put together and present slides right in O-Brain, so a pitch or a client update doesn’t mean bouncing to another tool. Everything stays in one place, on your brand.',
    points: ['Build and present in-app', 'Collaborative editing', 'On-brand output'],
  },
  {
    key: 'page-builder',
    group: 'Docs & content',
    name: 'Website',
    tagline: 'Publish a real website, generated by AI.',
    body: 'Describe the page you want and O-Brain builds it, then publishes it on your own domain with real visitor analytics. Forms on the page feed leads straight into your CRM.',
    points: ['AI-generated pages', 'Custom domain and analytics', 'Forms wired to the CRM'],
  },
  {
    key: 'forms',
    group: 'Docs & content',
    name: 'Forms',
    tagline: 'Turn your site into a lead source.',
    body: 'Build embeddable forms, or point an inbound webhook at O-Brain, and every submission lands as a contact — firing your follow-up automations the moment it arrives.',
    points: ['Embeddable forms and inbound webhook', 'Submissions become contacts', 'Triggers your automations'],
  },

  // ---- Storage ----
  {
    key: 'drive',
    group: 'Storage',
    name: 'Drive',
    tagline: 'Your files, organized and shareable.',
    body: 'Cloud storage with folders, versions and share-to-client links, sitting alongside the contacts and deals the files belong to. No more hunting through email attachments for the latest version.',
    points: ['Folders and version history', 'Share-to-client links', 'Attached to the right records'],
  },

  // ---- Automation & AI ----
  {
    key: 'workflows',
    group: 'Automation & AI',
    name: 'Workflows',
    tagline: 'Your follow-up, running itself.',
    body: 'Wire triggers to actions — when a proposal is won, a form is submitted, a tag is added — and O-Brain sends the email, fires the SMS, updates the tag or hits a webhook for you. Over 20 triggers are wired to real actions, not just notifications.',
    points: ['20+ real triggers', 'Email, SMS, tag and webhook actions', 'Runs 24/7 in the background'],
  },
  {
    key: 'intelligence',
    group: 'Automation & AI',
    name: 'O-Brain AI',
    tagline: 'An assistant that actually knows your business.',
    body: 'O-Brain chats with the full context of your business and can draft and send email or SMS — always with your confirmation first. Meetings become summaries, and a monthly Coach report scores your business health and flags your win/loss patterns.',
    points: ['Context-aware chat, drafts on your say-so', 'Meeting summaries and action items', 'Monthly health score, 1–100'],
  },

  // ---- Branding ----
  {
    key: 'branding',
    group: 'Branding',
    name: 'White-label',
    tagline: 'Make it yours, top to bottom.',
    body: 'The white-label option puts your logo, colors, fonts and domain across the entire workspace and the client portal — in both light and dark. Your clients see your brand, not ours.',
    points: ['Logo, colors and fonts (light + dark)', 'Custom domains', 'Branded client portal'],
  },
]

const GROUPS = [
  'Overview',
  'CRM & sales',
  'Accounting',
  'Communication',
  'Meetings & scheduling',
  'Docs & content',
  'Storage',
  'Automation & AI',
  'Branding',
]

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-')

export default function FeaturesPage() {
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [])

  let rowIndex = 0

  return (
    <div className="fp-root">
      <nav className="fp-nav">
        <Link className="fp-logo" to="/">
          O<span className="dot">·</span>Brain
        </Link>
        <div className="fp-nav-links">
          <Link to="/" className="fp-nav-anchor">Home</Link>
          <Link to="/#sp-pricing" className="fp-nav-anchor">Pricing</Link>
          <Link to="/login" className="fp-btn fp-btn-ghost">Log in</Link>
          <Link to="/register" className="fp-btn fp-btn-primary">Get started free</Link>
        </div>
      </nav>

      <header className="fp-hero">
        <p className="fp-eyebrow">Features</p>
        <h1 className="fp-hero-h1">Everything O-Brain does — and what each part is for.</h1>
        <p className="fp-hero-sub">
          One login replaces a stack of tools that never talked to each other. Here’s every module,
          what it actually does, and why it earns its place — shown on real screens from a working
          workspace.
        </p>
        <div className="fp-jump">
          {GROUPS.map((g) => (
            <a key={g} href={`#${slug(g)}`} className="fp-jump-pill">
              {g}
            </a>
          ))}
        </div>
      </header>

      <main>
        {GROUPS.map((group) => {
          const items = FEATURES.filter((f) => f.group === group)
          if (!items.length) return null
          return (
            <section key={group} className="fp-group" id={slug(group)}>
              <div className="fp-group-head">
                <h2>{group}</h2>
                <span className="fp-group-count">
                  {items.length} {items.length === 1 ? 'tool' : 'tools'}
                </span>
              </div>
              <div className="fp-rows">
                {items.map((f) => {
                  const reverse = rowIndex++ % 2 === 1
                  return (
                    <article key={f.key} className={`fp-row${reverse ? ' reverse' : ''}`}>
                      <div className="fp-shot">
                        <div className="fp-shot-frame">
                          <img
                            src={`/showcase/${f.key}.webp`}
                            alt={`${f.name} — real product screenshot`}
                            loading="lazy"
                            width={1600}
                            height={1000}
                          />
                        </div>
                      </div>
                      <div className="fp-copy">
                        <p className="fp-kicker">{f.group}</p>
                        <h3 className="fp-name">{f.name}</h3>
                        <p className="fp-tag">{f.tagline}</p>
                        <p className="fp-body">{f.body}</p>
                        <ul className="fp-points">
                          {f.points.map((p) => (
                            <li key={p}>
                              <svg viewBox="0 0 20 20" aria-hidden="true" width="18" height="18">
                                <path
                                  d="M4 10.5l3.5 3.5L16 6"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="2.2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                              <span>{p}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>
          )
        })}
      </main>

      <section className="fp-cta">
        <h2>All of it, behind one login.</h2>
        <p>
          Start on the free tier and turn on what you need — plans differ by usage, not by locking
          features away.
        </p>
        <div className="fp-cta-btns">
          <Link to="/register" className="fp-btn fp-btn-primary fp-btn-lg">
            Get started free
          </Link>
          <Link to="/#sp-pricing" className="fp-btn fp-btn-ghost fp-btn-lg">
            See pricing
          </Link>
        </div>
      </section>

      <footer className="fp-footer">
        <div>
          <Link to="/">Home</Link>
          <Link to="/login">Log in</Link>
          <Link to="/#sp-pricing">Pricing</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </div>
        <p>O-Brain — Your business, remembered. · An OCIDM product</p>
      </footer>
    </div>
  )
}
