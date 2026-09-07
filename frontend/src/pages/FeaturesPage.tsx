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
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

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
    body: i18n.t('ui:FeaturesPage.theMomentYouLogIn'),
    points: [i18n.t('ui:FeaturesPage.revenueOutstandingAndCashTrends'), i18n.t('ui:FeaturesPage.todaySMeetingsAndUpcoming'), i18n.t('ui:FeaturesPage.pendingApprovalsAndUnreadMessages')],
  },

  // ---- CRM & sales ----
  {
    key: 'contacts',
    group: 'CRM & sales',
    name: 'Contacts',
    tagline: 'A CRM that remembers every conversation.',
    body: i18n.t('ui:FeaturesPage.eachContactCarriesAFull'),
    points: [i18n.t('ui:FeaturesPage.completeInteractionHistoryPerContact'), i18n.t('ui:FeaturesPage.privatePerEmployeeBooksShared'), i18n.t('ui:FeaturesPage.anAiWrittenBriefBefore')],
  },
  {
    key: 'pipeline',
    group: 'CRM & sales',
    name: 'Pipeline',
    tagline: 'Every deal, staged from first touch to won.',
    body: i18n.t('ui:FeaturesPage.dragDealsThroughYourStages'),
    points: [i18n.t('ui:FeaturesPage.stageByStageTotals'), i18n.t('ui:FeaturesPage.dragAndDropDealManagement'), i18n.t('ui:FeaturesPage.oneClickFromWonTo')],
  },
  {
    key: 'proposals',
    group: 'CRM & sales',
    name: 'Proposals',
    tagline: 'E-signature proposals that become invoices when won.',
    body: i18n.t('ui:FeaturesPage.sendABrandedItemizedProposal'),
    points: [i18n.t('ui:FeaturesPage.legallyBindingESignature'), i18n.t('ui:FeaturesPage.autoConvertsToAnInvoice'), i18n.t('ui:FeaturesPage.trackOpenedSignedAndPaid')],
  },
  {
    key: 'estimates',
    group: 'CRM & sales',
    name: 'Estimates',
    tagline: 'Quotes that convert in a single click.',
    body: i18n.t('ui:FeaturesPage.buildAQuoteSendIt'),
    points: [i18n.t('ui:FeaturesPage.reusableLineItems'), i18n.t('ui:FeaturesPage.oneClickConvertToInvoice'), i18n.t('ui:FeaturesPage.acceptAndDeclineTracking')],
  },
  {
    key: 'invoices',
    group: 'CRM & sales',
    name: 'Invoices',
    tagline: 'Get paid faster, chase less.',
    body: i18n.t('ui:FeaturesPage.everyInvoiceIsAClean'),
    points: [i18n.t('ui:FeaturesPage.stripePayNowOnEvery'), i18n.t('ui:FeaturesPage.automaticPaymentReminders'), i18n.t('ui:FeaturesPage.partialPaymentsAndOverdueDetection')],
  },

  // ---- Accounting ----
  {
    key: 'cashbook',
    group: 'Accounting',
    name: 'Cashbook',
    tagline: 'Every dollar in and out — personal and business kept apart.',
    body: i18n.t('ui:FeaturesPage.theCashbookIsTheHeart'),
    points: [i18n.t('ui:FeaturesPage.oneLedgerReconciledToThe'), i18n.t('ui:FeaturesPage.personalVsBusinessTaggingFrom'), i18n.t('ui:FeaturesPage.ownerSDrawHandlingKeeps')],
  },
  {
    key: 'reconcile',
    group: 'Accounting',
    name: 'Reconcile',
    tagline: 'Prove your books match the bank.',
    body: i18n.t('ui:FeaturesPage.reconciliationPutsYourRecordedBalance'),
    points: [i18n.t('ui:FeaturesPage.bookVsBankBalanceSide'), i18n.t('ui:FeaturesPage.instantDriftDetection'), i18n.t('ui:FeaturesPage.matchClearAndLockA')],
  },
  {
    key: 'bank-feeds',
    group: 'Accounting',
    name: i18n.t('ui:FeaturesPage.bankFeeds'),
    tagline: 'Live transactions, straight from the bank.',
    body: i18n.t('ui:FeaturesPage.connectYourAccountsThroughPlaid'),
    points: [i18n.t('ui:FeaturesPage.secureBankConnectionViaPlaid'), i18n.t('ui:FeaturesPage.autoSyncingTransactions'), i18n.t('ui:FeaturesPage.bulkCategorizeWithSavedRules')],
  },
  {
    key: 'email-scanner',
    group: 'Accounting',
    name: i18n.t('ui:FeaturesPage.emailScanner'),
    tagline: 'Invoices and receipts, read out of your inbox.',
    body: i18n.t('ui:FeaturesPage.pointOBrainAtGmail'),
    points: [i18n.t('ui:FeaturesPage.scansGmailForInvoicesAnd'), i18n.t('ui:FeaturesPage.extractsAmountVendorAndTax'), i18n.t('ui:FeaturesPage.filesAsExpenseOrIncome')],
  },
  {
    key: 'receipt-capture',
    group: 'Accounting',
    name: 'Receipts',
    tagline: 'Snap it and forget it.',
    body: i18n.t('ui:FeaturesPage.photographAReceiptAndO'),
    points: [i18n.t('ui:FeaturesPage.photoToStructuredData'), i18n.t('ui:FeaturesPage.autoAttachedToTheTransaction'), i18n.t('ui:FeaturesPage.auditReadyRecordKeeping')],
  },
  {
    key: 'smart-import',
    group: 'Accounting',
    name: i18n.t('ui:FeaturesPage.smartImport'),
    tagline: 'Drop in a statement, get a clean ledger.',
    body: i18n.t('ui:FeaturesPage.uploadACsvOrPdf'),
    points: [i18n.t('ui:FeaturesPage.csvAndPdfStatements'), i18n.t('ui:FeaturesPage.aiColumnMapping'), i18n.t('ui:FeaturesPage.learnsYourCategorization')],
  },
  {
    key: 'expenses',
    group: 'Accounting',
    name: 'Expenses',
    tagline: 'Spending you can actually control.',
    body: i18n.t('ui:FeaturesPage.trackCategorizedExpensesWithReceipts'),
    points: [i18n.t('ui:FeaturesPage.categorizedSpendingWithReceipts'), i18n.t('ui:FeaturesPage.approvalWorkflows'), i18n.t('ui:FeaturesPage.vendorAndCategoryBreakdowns')],
  },
  {
    key: 'income',
    group: 'Accounting',
    name: 'Income',
    tagline: 'Every payment tied to where it came from.',
    body: i18n.t('ui:FeaturesPage.recordIncomeAgainstTheClient'),
    points: [i18n.t('ui:FeaturesPage.paymentsLinkedToClientAnd'), i18n.t('ui:FeaturesPage.cleanRevenueAttribution'), i18n.t('ui:FeaturesPage.feedsYourPLAutomatically')],
  },
  {
    key: 'recurring',
    group: 'Accounting',
    name: 'Recurring',
    tagline: 'Set the regulars once.',
    body: i18n.t('ui:FeaturesPage.rentSoftwareRetainersAndAnything'),
    points: [i18n.t('ui:FeaturesPage.scheduledRecurringEntries'), i18n.t('ui:FeaturesPage.incomeOrExpense'), i18n.t('ui:FeaturesPage.neverMissARegular')],
  },
  {
    key: 'budgets',
    group: 'Accounting',
    name: 'Budgets',
    tagline: 'A plan you can watch in real time.',
    body: i18n.t('ui:FeaturesPage.setABudgetPerCategory'),
    points: [i18n.t('ui:FeaturesPage.perCategoryBudgets'), i18n.t('ui:FeaturesPage.liveActualVsPlan'), i18n.t('ui:FeaturesPage.earlyOverspendWarning')],
  },
  {
    key: 'reports',
    group: 'Accounting',
    name: 'Reports',
    tagline: 'The statements your accountant asks for, always current.',
    body: i18n.t('ui:FeaturesPage.pLBalanceSheetCash'),
    points: [i18n.t('ui:FeaturesPage.pLBalanceSheetAnd'), i18n.t('ui:FeaturesPage.salesTaxGstHstAnd'), i18n.t('ui:FeaturesPage.exportReadyAnyTime')],
  },

  // ---- Communication ----
  {
    key: 'inbox',
    group: 'Communication',
    name: 'Inbox',
    tagline: 'Every conversation in one thread.',
    body: i18n.t('ui:FeaturesPage.emailAndSmsLandIn'),
    points: [i18n.t('ui:FeaturesPage.emailAndSmsUnified'), i18n.t('ui:FeaturesPage.threadedByContact'), i18n.t('ui:FeaturesPage.repliesLoggedToTheCrm')],
  },
  {
    key: 'phone',
    group: 'Communication',
    name: 'Phone',
    tagline: 'A phone system built into your browser.',
    body: i18n.t('ui:FeaturesPage.makeAndTakeCallsRight'),
    points: [i18n.t('ui:FeaturesPage.browserCallingOnTwilio'), i18n.t('ui:FeaturesPage.voicemailTranscription'), i18n.t('ui:FeaturesPage.callLoggingAndADial')],
  },

  // ---- Meetings & scheduling ----
  {
    key: 'meetings',
    group: 'Meetings & scheduling',
    name: 'Meetings',
    tagline: 'Video calls that take their own notes.',
    body: i18n.t('ui:FeaturesPage.runVideoMeetingsInThe'),
    points: [i18n.t('ui:FeaturesPage.browserVideoRoomsOnLivekit'), i18n.t('ui:FeaturesPage.aiTranscriptSummaryAndAction'), i18n.t('ui:FeaturesPage.draftAQuoteFromThe')],
  },
  {
    key: 'calendar',
    group: 'Meetings & scheduling',
    name: 'Calendar',
    tagline: 'One calendar, synced both ways with Google.',
    body: i18n.t('ui:FeaturesPage.yourBookingsAndEventsLive'),
    points: [i18n.t('ui:FeaturesPage.twoWayGoogleCalendarSync'), i18n.t('ui:FeaturesPage.bookingsAndEventsInOne'), i18n.t('ui:FeaturesPage.noDoubleBooking')],
  },
  {
    key: 'scheduling',
    group: 'Meetings & scheduling',
    name: 'Scheduling',
    tagline: 'Let clients book you without the back-and-forth.',
    body: i18n.t('ui:FeaturesPage.shareABookingPageAnd'),
    points: [i18n.t('ui:FeaturesPage.shareableBookingPages'), i18n.t('ui:FeaturesPage.autoConfirmationsAndReminders'), i18n.t('ui:FeaturesPage.feedsYourSyncedCalendar')],
  },

  // ---- Docs & content ----
  {
    key: 'docs',
    group: 'Docs & content',
    name: 'Docs',
    tagline: 'Real-time documents, no Google account needed.',
    body: i18n.t('ui:FeaturesPage.writeAndCollaborateOnDocuments'),
    points: [i18n.t('ui:FeaturesPage.liveMultiUserEditing'), i18n.t('ui:FeaturesPage.autosaveAndVersionHistory'), i18n.t('ui:FeaturesPage.shareByLink')],
  },
  {
    key: 'sheets',
    group: 'Docs & content',
    name: 'Sheets',
    tagline: 'Spreadsheets that live with your data.',
    body: i18n.t('ui:FeaturesPage.buildSpreadsheetsWithFormulasShared'),
    points: [i18n.t('ui:FeaturesPage.formulasAndLiveCollaboration'), i18n.t('ui:FeaturesPage.sharedInYourWorkspace'), i18n.t('ui:FeaturesPage.noExtraLogin')],
  },
  {
    key: 'slides',
    group: 'Docs & content',
    name: 'Slides',
    tagline: 'Decks without leaving the workspace.',
    body: i18n.t('ui:FeaturesPage.putTogetherAndPresentSlides'),
    points: [i18n.t('ui:FeaturesPage.buildAndPresentInApp'), i18n.t('ui:FeaturesPage.collaborativeEditing'), i18n.t('ui:FeaturesPage.onBrandOutput')],
  },
  {
    key: 'page-builder',
    group: 'Docs & content',
    name: 'Website',
    tagline: 'Publish a real website, generated by AI.',
    body: i18n.t('ui:FeaturesPage.describeThePageYouWant'),
    points: [i18n.t('ui:FeaturesPage.aiGeneratedPages'), i18n.t('ui:FeaturesPage.customDomainAndAnalytics'), i18n.t('ui:FeaturesPage.formsWiredToTheCrm')],
  },
  {
    key: 'forms',
    group: 'Docs & content',
    name: 'Forms',
    tagline: 'Turn your site into a lead source.',
    body: i18n.t('ui:FeaturesPage.buildEmbeddableFormsOrPoint'),
    points: [i18n.t('ui:FeaturesPage.embeddableFormsAndInboundWebhook'), i18n.t('ui:FeaturesPage.submissionsBecomeContacts'), i18n.t('ui:FeaturesPage.triggersYourAutomations')],
  },

  // ---- Storage ----
  {
    key: 'drive',
    group: 'Storage',
    name: 'Drive',
    tagline: 'Your files, organized and shareable.',
    body: i18n.t('ui:FeaturesPage.cloudStorageWithFoldersVersions'),
    points: [i18n.t('ui:FeaturesPage.foldersAndVersionHistory'), i18n.t('ui:FeaturesPage.shareToClientLinks'), i18n.t('ui:FeaturesPage.attachedToTheRightRecords')],
  },

  // ---- Automation & AI ----
  {
    key: 'workflows',
    group: 'Automation & AI',
    name: 'Workflows',
    tagline: 'Your follow-up, running itself.',
    body: i18n.t('ui:FeaturesPage.wireTriggersToActionsWhen'),
    points: [i18n.t('ui:FeaturesPage.n20RealTriggers'), i18n.t('ui:FeaturesPage.emailSmsTagAndWebhook'), i18n.t('ui:FeaturesPage.runs247InThe')],
  },
  {
    key: 'intelligence',
    group: 'Automation & AI',
    name: i18n.t('ui:FeaturesPage.oBrainAi'),
    tagline: 'An assistant that actually knows your business.',
    body: i18n.t('ui:FeaturesPage.oBrainChatsWithThe'),
    points: [i18n.t('ui:FeaturesPage.contextAwareChatDraftsOn'), i18n.t('ui:FeaturesPage.meetingSummariesAndActionItems'), i18n.t('ui:FeaturesPage.monthlyHealthScore1100')],
  },

  // ---- Branding ----
  {
    key: 'branding',
    group: 'Branding',
    name: 'White-label',
    tagline: 'Make it yours, top to bottom.',
    body: i18n.t('ui:FeaturesPage.theWhiteLabelOptionPuts'),
    points: [i18n.t('ui:FeaturesPage.logoColorsAndFontsLight'), i18n.t('ui:FeaturesPage.customDomains'), i18n.t('ui:FeaturesPage.brandedClientPortal')],
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
  const { t } = useTranslation('ui')
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [])

  let rowIndex = 0

  return (
    <div className="fp-root">
      <nav className="fp-nav">
        <Link className="fp-logo" to="/">
          O<span className="dot">·</span>{t('ui:FeaturesPage.brain')}
        </Link>
        <div className="fp-nav-links">
          <Link to="/" className="fp-nav-anchor">{t('ui:FeaturesPage.home')}</Link>
          <Link to="/#sp-pricing" className="fp-nav-anchor">{t('ui:FeaturesPage.pricing')}</Link>
          <Link to="/login" className="fp-btn fp-btn-ghost">{t('ui:FeaturesPage.logIn')}</Link>
          <Link to="/register" className="fp-btn fp-btn-primary">{t('ui:FeaturesPage.getStartedFree')}</Link>
        </div>
      </nav>

      <header className="fp-hero">
        <p className="fp-eyebrow">{t('ui:FeaturesPage.features')}</p>
        <h1 className="fp-hero-h1">{t('ui:FeaturesPage.everythingOBrainDoesAnd')}</h1>
        <p className="fp-hero-sub">
         {t('ui:FeaturesPage.oneLoginReplacesAStack')}
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
                            alt={t('ui:FeaturesPage.nameRealProductScreenshot', { name: f.name })}
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
        <h2>{t('ui:FeaturesPage.allOfItBehindOne')}</h2>
        <p>
         {t('ui:FeaturesPage.startOnTheFreeTier')}
        </p>
        <div className="fp-cta-btns">
          <Link to="/register" className="fp-btn fp-btn-primary fp-btn-lg">
           {t('ui:FeaturesPage.getStartedFree')}
          </Link>
          <Link to="/#sp-pricing" className="fp-btn fp-btn-ghost fp-btn-lg">
           {t('ui:FeaturesPage.seePricing')}
          </Link>
        </div>
      </section>

      <footer className="fp-footer">
        <div>
          <Link to="/">{t('ui:FeaturesPage.home')}</Link>
          <Link to="/login">{t('ui:FeaturesPage.logIn')}</Link>
          <Link to="/#sp-pricing">{t('ui:FeaturesPage.pricing')}</Link>
          <Link to="/privacy">{t('ui:FeaturesPage.privacy')}</Link>
          <Link to="/terms">{t('ui:FeaturesPage.terms')}</Link>
        </div>
        <p>{t('ui:FeaturesPage.oBrainYourBusinessRemembered')}</p>
      </footer>
    </div>
  )
}
