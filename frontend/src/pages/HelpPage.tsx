import { useState } from 'react'
import {
  LayoutDashboard,
  FileText,
  Users,
  FileOutput,
  ClipboardList,
  BookOpen,
  Receipt,
  TrendingUp,
  RefreshCw,
  PiggyBank,
  BarChart3,
  Inbox,
  Landmark,
  Camera,
  Calendar,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

interface FeatureSection {
  id: string
  title: string
  icon: React.ComponentType<{ className?: string }>
  description: string
  features: string[]
  gettingStarted: string
}

const sections: FeatureSection[] = [
  {
    id: 'dashboard',
    title: i18n.t('ui:HelpPage.dashboard'),
    icon: LayoutDashboard,
    description:
      i18n.t('ui:HelpPage.theDashboardProvidesAHigh'),
    features: [
      i18n.t('ui:HelpPage.viewKeyFinancialStatsSuch'),
      i18n.t('ui:HelpPage.activityFeedShowingRecentDocument'),
      i18n.t('ui:HelpPage.pendingApprovalsSectionForInvoices'),
      i18n.t('ui:HelpPage.upcomingDeadlinesWidgetHighlightingInvoi'),
      i18n.t('ui:HelpPage.quickActionButtonsToCreate'),
    ],
    gettingStarted:
      'Your dashboard populates automatically as you add invoices, expenses, and documents. Start by creating your first invoice or uploading a receipt to see your stats come to life.',
  },
  {
    id: 'documents',
    title: i18n.t('ui:HelpPage.documents'),
    icon: FileText,
    description:
      i18n.t('ui:HelpPage.theDocumentsVaultLetsYou'),
    features: [
      i18n.t('ui:HelpPage.uploadPdfsImagesJpgPng'),
      i18n.t('ui:HelpPage.organizeDocumentsIntoFoldersFor'),
      i18n.t('ui:HelpPage.tagDocumentsWithCustomLabels'),
      i18n.t('ui:HelpPage.aiPoweredDataExtractionAutomatically'),
      i18n.t('ui:HelpPage.previewDocumentsDirectlyInThe'),
      i18n.t('ui:HelpPage.linkDocumentsToInvoicesExpenses'),
    ],
    gettingStarted:
      'Navigate to the Documents page and click "Upload" to add your first file. The AI extraction engine will automatically attempt to identify amounts, dates, and vendor information.',
  },
  {
    id: 'contacts',
    title: i18n.t('ui:HelpPage.contacts'),
    icon: Users,
    description:
      i18n.t('ui:HelpPage.contactsServesAsYourCustomer'),
    features: [
      i18n.t('ui:HelpPage.storeContactDetailsIncludingName'),
      i18n.t('ui:HelpPage.categorizeContactsAsCustomersVendors'),
      i18n.t('ui:HelpPage.viewAllInvoicesAndExpenses'),
      i18n.t('ui:HelpPage.searchAndFilterContactsBy'),
      i18n.t('ui:HelpPage.importContactsOrAddThem'),
    ],
    gettingStarted:
      'Add your first contact by clicking "New Contact" and filling in their details. Once created, you can select them when creating invoices or recording expenses.',
  },
  {
    id: 'invoices',
    title: i18n.t('ui:HelpPage.invoices'),
    icon: FileOutput,
    description:
      i18n.t('ui:HelpPage.createProfessionalInvoicesWithLine'),
    features: [
      i18n.t('ui:HelpPage.createInvoicesWithMultipleLine'),
      i18n.t('ui:HelpPage.automaticTaxCalculationWithConfigurable'),
      i18n.t('ui:HelpPage.trackInvoiceStatusDraftSent'),
      i18n.t('ui:HelpPage.sendInvoicesDirectlyToCustomers'),
      i18n.t('ui:HelpPage.generateAndDownloadProfessionalPdf'),
      i18n.t('ui:HelpPage.issueCreditNotesAgainstExisting'),
    ],
    gettingStarted:
      'Go to Invoices and click "New Invoice." Select a contact, add your line items, and choose whether to save as draft or send immediately.',
  },
  {
    id: 'estimates',
    title: i18n.t('ui:HelpPage.estimates'),
    icon: ClipboardList,
    description:
      i18n.t('ui:HelpPage.createDetailedQuotesAndEstimates'),
    features: [
      i18n.t('ui:HelpPage.buildEstimatesWithItemizedLine'),
      i18n.t('ui:HelpPage.trackEstimateStatusDraftSent'),
      i18n.t('ui:HelpPage.convertAcceptedEstimatesIntoInvoices'),
      i18n.t('ui:HelpPage.sendEstimatesToClientsVia'),
      i18n.t('ui:HelpPage.duplicateExistingEstimatesToQuickly'),
    ],
    gettingStarted:
      'Create a new estimate from the Estimates page, add your line items and pricing, then send it to your client. Once accepted, use the "Convert to Invoice" action to generate the invoice.',
  },
  {
    id: 'cashbook',
    title: i18n.t('ui:HelpPage.cashbook'),
    icon: BookOpen,
    description:
      i18n.t('ui:HelpPage.theCashbookIsYourUnified'),
    features: [
      i18n.t('ui:HelpPage.unifiedLedgerDisplayingAllIncome'),
      i18n.t('ui:HelpPage.supportForMultiplePaymentAccounts'),
      i18n.t('ui:HelpPage.automaticHstGstSplitCalculation'),
      i18n.t('ui:HelpPage.runningBalanceThatUpdatesIn'),
      i18n.t('ui:HelpPage.excelImportFunctionalityToBulk'),
      i18n.t('ui:HelpPage.categorizeEntriesUsing31Built'),
    ],
    gettingStarted:
      'Start by adding your payment accounts, then record your first transaction. You can also import transactions in bulk from an Excel file exported from your bank.',
  },
  {
    id: 'expenses',
    title: i18n.t('ui:HelpPage.expenses'),
    icon: Receipt,
    description:
      i18n.t('ui:HelpPage.trackAllBusinessExpensesWith'),
    features: [
      i18n.t('ui:HelpPage.recordExpensesWithVendorAmount'),
      i18n.t('ui:HelpPage.attachReceiptImagesOrPdfs'),
      i18n.t('ui:HelpPage.categorizeExpensesForAccurateFinancial'),
      i18n.t('ui:HelpPage.dashboardAnalyticsShowingSpendingTrends'),
      i18n.t('ui:HelpPage.filterAndSearchExpensesBy'),
    ],
    gettingStarted:
      'Click "New Expense" to record a purchase. Fill in the vendor, amount, and category, then optionally attach a photo of the receipt for your records.',
  },
  {
    id: 'income',
    title: i18n.t('ui:HelpPage.income'),
    icon: TrendingUp,
    description:
      i18n.t('ui:HelpPage.recordAllIncomeEntriesTo'),
    features: [
      i18n.t('ui:HelpPage.recordIncomeEntriesWithSource'),
      i18n.t('ui:HelpPage.linkIncomeToSpecificContacts'),
      i18n.t('ui:HelpPage.incomeDataFeedsAutomaticallyInto'),
      i18n.t('ui:HelpPage.filterIncomeByDateRange'),
      i18n.t('ui:HelpPage.viewIncomeTrendsAndTotals'),
    ],
    gettingStarted:
      'Navigate to the Income page and click "New Income" to record a payment received. Link it to an invoice if applicable to keep your records consistent.',
  },
  {
    id: 'recurring',
    title: i18n.t('ui:HelpPage.recurring'),
    icon: RefreshCw,
    description:
      i18n.t('ui:HelpPage.setUpRecurringRulesTo'),
    features: [
      i18n.t('ui:HelpPage.createRecurringRulesWithDaily'),
      i18n.t('ui:HelpPage.autoGeneratesIncomeOrExpense'),
      i18n.t('ui:HelpPage.configureStartAndOptionalEnd'),
      i18n.t('ui:HelpPage.pauseOrResumeRecurringRules'),
      i18n.t('ui:HelpPage.viewUpcomingScheduledTransactionsOn'),
    ],
    gettingStarted:
      'Go to the Recurring page and create a new rule. Choose the frequency, set the amount and category, and the system will automatically generate transactions on schedule.',
  },
  {
    id: 'budgets',
    title: i18n.t('ui:HelpPage.budgets'),
    icon: PiggyBank,
    description:
      i18n.t('ui:HelpPage.setCategoryLevelBudgetsWith'),
    features: [
      i18n.t('ui:HelpPage.createBudgetsForSpecificExpense'),
      i18n.t('ui:HelpPage.trackActualSpendingVsBudgeted'),
      i18n.t('ui:HelpPage.visualProgressBarsShowingHow'),
      i18n.t('ui:HelpPage.setBudgetPeriodsMonthlyQuarterly'),
      i18n.t('ui:HelpPage.receiveAlertsWhenSpendingApproaches'),
    ],
    gettingStarted:
      'Create your first budget by selecting a category, setting a spending limit, and choosing the budget period. As you record expenses, the budget tracker will update automatically.',
  },
  {
    id: 'reports',
    title: i18n.t('ui:HelpPage.reports'),
    icon: BarChart3,
    description:
      i18n.t('ui:HelpPage.generateComprehensiveFinancialReportsInc'),
    features: [
      i18n.t('ui:HelpPage.profitLossReportShowingRevenue'),
      i18n.t('ui:HelpPage.taxSummaryReportWithHst'),
      i18n.t('ui:HelpPage.cashFlowReportTrackingMoney'),
      i18n.t('ui:HelpPage.accountsSummaryWithABreakdown'),
      i18n.t('ui:HelpPage.accountsReceivableAndAccountsPayable'),
      i18n.t('ui:HelpPage.exportAnyReportToPdf'),
    ],
    gettingStarted:
      'Visit the Reports page and select the report type you need. Choose a date range and click "Generate" to view your report. Use the PDF export button to download a copy.',
  },
  {
    id: 'email-scan',
    title: i18n.t('ui:HelpPage.emailScan'),
    icon: Inbox,
    description:
      i18n.t('ui:HelpPage.connectYourGmailAccountTo'),
    features: [
      i18n.t('ui:HelpPage.connectYourGmailAccountSecurely'),
      i18n.t('ui:HelpPage.automaticDetectionOfInvoiceAnd'),
      i18n.t('ui:HelpPage.importDetectedDocumentsDirectlyInto'),
      i18n.t('ui:HelpPage.reviewScannedDocumentsBeforeThey'),
      i18n.t('ui:HelpPage.configureScanFrequencyAndFiltering'),
    ],
    gettingStarted:
      'Go to Settings and connect your Gmail account under the Gmail integration section. Once connected, navigate to Email Scan to start scanning your inbox for financial documents.',
  },
  {
    id: 'banking',
    title: i18n.t('ui:HelpPage.banking'),
    icon: Landmark,
    description:
      i18n.t('ui:HelpPage.connectYourBankAccountsVia'),
    features: [
      i18n.t('ui:HelpPage.connectBankAccountsSecurelyThrough'),
      i18n.t('ui:HelpPage.automaticImportOfBankTransactions'),
      i18n.t('ui:HelpPage.createAutoCategorizationRulesTo'),
      i18n.t('ui:HelpPage.reviewAndApproveImportedTransactions'),
      i18n.t('ui:HelpPage.supportForMultipleBankAccounts'),
    ],
    gettingStarted:
      'Navigate to Banking and click "Connect Account" to link your bank via Plaid. Once connected, transactions will be imported automatically and you can set up rules to categorize them.',
  },
  {
    id: 'capture',
    title: i18n.t('ui:HelpPage.capture'),
    icon: Camera,
    description:
      i18n.t('ui:HelpPage.useTheMobileFriendlyCapture'),
    features: [
      i18n.t('ui:HelpPage.mobileOptimizedInterfaceForQuick'),
      i18n.t('ui:HelpPage.aiPoweredExtractionReadsVendor'),
      i18n.t('ui:HelpPage.automaticallyCreatesAnExpenseEntry'),
      i18n.t('ui:HelpPage.reviewAndEditExtractedDetails'),
      i18n.t('ui:HelpPage.capturedImagesAreStoredIn'),
    ],
    gettingStarted:
      'Open the Capture page on your phone, take a photo of a receipt, and the AI will extract the details. Review the information, make any corrections, and save to create an expense automatically.',
  },
  {
    id: 'calendar',
    title: i18n.t('ui:HelpPage.calendar'),
    icon: Calendar,
    description:
      i18n.t('ui:HelpPage.theCalendarGivesYouA'),
    features: [
      i18n.t('ui:HelpPage.monthlyCalendarViewShowingAll'),
      i18n.t('ui:HelpPage.invoiceDueDatesDisplayedWith'),
      i18n.t('ui:HelpPage.recurringTransactionDatesMarkedOn'),
      i18n.t('ui:HelpPage.budgetPeriodStartAndEnd'),
      i18n.t('ui:HelpPage.clickAnyDateToSee'),
    ],
    gettingStarted:
      'Visit the Calendar page to see all your upcoming financial dates. Invoices, recurring transactions, and budget periods are displayed automatically based on your existing data.',
  },
  {
    id: 'settings',
    title: i18n.t('ui:HelpPage.settings'),
    icon: Settings,
    description:
      i18n.t('ui:HelpPage.configureYourAccountAndApplication'),
    features: [
      i18n.t('ui:HelpPage.profileSettingsForUpdatingYour'),
      i18n.t('ui:HelpPage.userManagementForAddingTeam'),
      i18n.t('ui:HelpPage.emailConfigurationForOutgoingInvoice'),
      i18n.t('ui:HelpPage.gmailAndBankingIntegrationSetup'),
      i18n.t('ui:HelpPage.taxRateConfigurationForHst'),
      i18n.t('ui:HelpPage.paymentReminderSchedulesSmsNotifications'),
    ],
    gettingStarted:
      'Start with the Profile section to ensure your business details are correct, then configure your tax rates under the Tax tab. Connect your email and banking integrations as needed.',
  },
]

export default function HelpPage() {
  const { t } = useTranslation('ui')
  const [activeSection, setActiveSection] = useState(sections[0].id)

  const handleNavClick = (id: string) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">{t('ui:HelpPage.helpDocumentation')}</h1>

      <div className="flex gap-8">
        {/* Left sidebar navigation */}
        <nav className="w-64 shrink-0 sticky top-6 self-start">
          <div className="space-y-1">
            {sections.map((section) => {
              const Icon = section.icon
              return (
                <button
                  key={section.id}
                  onClick={() => handleNavClick(section.id)}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md text-left transition-colors',
                    activeSection === section.id
                      ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100'
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{section.title}</span>
                </button>
              )
            })}
          </div>
        </nav>

        {/* Right content area */}
        <main className="min-w-0 flex-1">
          {sections.map((section) => {
            const Icon = section.icon
            return (
              <section
                key={section.id}
                id={section.id}
                className="scroll-mt-6 mb-12"
              >
                <h2 className="text-xl font-semibold flex items-center gap-2 mb-3">
                  <Icon className="h-5 w-5" />
                  {section.title}
                </h2>

                <p className="text-gray-700 dark:text-gray-300 mb-4">{section.description}</p>

                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
                 {t('ui:HelpPage.keyFeatures')}
                </h3>
                <ul className="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 mb-4">
                  {section.features.map((feature, index) => (
                    <li key={index}>{feature}</li>
                  ))}
                </ul>

                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
                 {t('ui:HelpPage.gettingStarted')}
                </h3>
                <p className="text-gray-600 dark:text-gray-400">{section.gettingStarted}</p>
              </section>
            )
          })}
        </main>
      </div>
    </div>
  )
}
