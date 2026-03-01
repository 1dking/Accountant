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
    title: 'Dashboard',
    icon: LayoutDashboard,
    description:
      'The Dashboard provides a high-level overview of your business finances, recent activity, and items that need your attention. It is the first page you see after logging in.',
    features: [
      'View key financial stats such as total revenue, expenses, and outstanding invoices at a glance.',
      'Activity feed showing recent document uploads, invoice creations, and payment recordings.',
      'Pending approvals section for invoices, estimates, and expenses awaiting action.',
      'Upcoming deadlines widget highlighting invoices due soon and recurring transactions.',
      'Quick-action buttons to create new invoices, record expenses, or upload documents.',
    ],
    gettingStarted:
      'Your dashboard populates automatically as you add invoices, expenses, and documents. Start by creating your first invoice or uploading a receipt to see your stats come to life.',
  },
  {
    id: 'documents',
    title: 'Documents',
    icon: FileText,
    description:
      'The Documents vault lets you upload, organize, and manage all your business files in one place. It supports PDFs, images, and other common file types up to 50MB each.',
    features: [
      'Upload PDFs, images (JPG, PNG), and other documents up to 50MB per file.',
      'Organize documents into folders for easy browsing and retrieval.',
      'Tag documents with custom labels for powerful filtering and search.',
      'AI-powered data extraction automatically pulls key information from uploaded invoices and receipts.',
      'Preview documents directly in the browser without downloading.',
      'Link documents to invoices, expenses, or contacts for full traceability.',
    ],
    gettingStarted:
      'Navigate to the Documents page and click "Upload" to add your first file. The AI extraction engine will automatically attempt to identify amounts, dates, and vendor information.',
  },
  {
    id: 'contacts',
    title: 'Contacts',
    icon: Users,
    description:
      'Contacts serves as your customer and vendor directory, storing all the details you need to create invoices, track expenses, and communicate with your business relationships.',
    features: [
      'Store contact details including name, email, phone number, and company.',
      'Categorize contacts as customers, vendors, or both.',
      'View all invoices and expenses linked to a specific contact.',
      'Search and filter contacts by name, company, or category.',
      'Import contacts or add them manually with a quick-entry form.',
    ],
    gettingStarted:
      'Add your first contact by clicking "New Contact" and filling in their details. Once created, you can select them when creating invoices or recording expenses.',
  },
  {
    id: 'invoices',
    title: 'Invoices',
    icon: FileOutput,
    description:
      'Create professional invoices with line items, tax calculations, and status tracking. Send invoices via email and generate PDF copies for your records.',
    features: [
      'Create invoices with multiple line items, quantities, rates, and descriptions.',
      'Automatic tax calculation with configurable HST/GST rates.',
      'Track invoice status: Draft, Sent, Viewed, Paid, Overdue, or Cancelled.',
      'Send invoices directly to customers via email with a single click.',
      'Generate and download professional PDF invoices.',
      'Issue credit notes against existing invoices for refunds or adjustments.',
    ],
    gettingStarted:
      'Go to Invoices and click "New Invoice." Select a contact, add your line items, and choose whether to save as draft or send immediately.',
  },
  {
    id: 'estimates',
    title: 'Estimates',
    icon: ClipboardList,
    description:
      'Create detailed quotes and estimates for potential work. When a client accepts an estimate, convert it directly into an invoice with one click.',
    features: [
      'Build estimates with itemized line items, quantities, and pricing.',
      'Track estimate status: Draft, Sent, Accepted, Declined, or Expired.',
      'Convert accepted estimates into invoices instantly, carrying over all line items.',
      'Send estimates to clients via email for review and approval.',
      'Duplicate existing estimates to quickly create similar quotes.',
    ],
    gettingStarted:
      'Create a new estimate from the Estimates page, add your line items and pricing, then send it to your client. Once accepted, use the "Convert to Invoice" action to generate the invoice.',
  },
  {
    id: 'cashbook',
    title: 'Cashbook',
    icon: BookOpen,
    description:
      'The Cashbook is your unified ledger for all financial transactions. It supports multiple payment accounts, automatic HST/GST splitting, and provides a running balance view.',
    features: [
      'Unified ledger displaying all income and expense transactions in one place.',
      'Support for multiple payment accounts (bank, cash, credit card, etc.).',
      'Automatic HST/GST split calculation on transactions.',
      'Running balance that updates in real time as entries are added.',
      'Excel import functionality to bulk-load transactions from bank statements.',
      'Categorize entries using 31 built-in categories for detailed financial tracking.',
    ],
    gettingStarted:
      'Start by adding your payment accounts, then record your first transaction. You can also import transactions in bulk from an Excel file exported from your bank.',
  },
  {
    id: 'expenses',
    title: 'Expenses',
    icon: Receipt,
    description:
      'Track all business expenses with vendor details, amounts, and categories. Attach receipt images for documentation and view spending analytics on the dashboard.',
    features: [
      'Record expenses with vendor, amount, date, and category fields.',
      'Attach receipt images or PDFs as supporting documentation.',
      'Categorize expenses for accurate financial reporting.',
      'Dashboard analytics showing spending trends and category breakdowns.',
      'Filter and search expenses by date range, vendor, or category.',
    ],
    gettingStarted:
      'Click "New Expense" to record a purchase. Fill in the vendor, amount, and category, then optionally attach a photo of the receipt for your records.',
  },
  {
    id: 'income',
    title: 'Income',
    icon: TrendingUp,
    description:
      'Record all income entries to maintain a complete picture of your revenue. Income records feed directly into Profit & Loss and tax reports.',
    features: [
      'Record income entries with source, amount, date, and category.',
      'Link income to specific contacts or invoices for traceability.',
      'Income data feeds automatically into P&L and tax summary reports.',
      'Filter income by date range, source, or category.',
      'View income trends and totals on the dashboard.',
    ],
    gettingStarted:
      'Navigate to the Income page and click "New Income" to record a payment received. Link it to an invoice if applicable to keep your records consistent.',
  },
  {
    id: 'recurring',
    title: 'Recurring',
    icon: RefreshCw,
    description:
      'Set up recurring rules to automatically generate transactions on a schedule. Supports daily, weekly, monthly, and yearly frequencies to save time on repetitive entries.',
    features: [
      'Create recurring rules with daily, weekly, monthly, or yearly frequencies.',
      'Auto-generates income or expense transactions based on your schedule.',
      'Configure start and optional end dates for each recurring rule.',
      'Pause or resume recurring rules at any time.',
      'View upcoming scheduled transactions on the Calendar page.',
    ],
    gettingStarted:
      'Go to the Recurring page and create a new rule. Choose the frequency, set the amount and category, and the system will automatically generate transactions on schedule.',
  },
  {
    id: 'budgets',
    title: 'Budgets',
    icon: PiggyBank,
    description:
      'Set category-level budgets with spending limits and track your actual spending against those targets. Stay on top of your finances with clear progress indicators.',
    features: [
      'Create budgets for specific expense categories with spending limits.',
      'Track actual spending vs. budgeted amounts in real time.',
      'Visual progress bars showing how much of each budget has been used.',
      'Set budget periods (monthly, quarterly, or yearly).',
      'Receive alerts when spending approaches or exceeds budget thresholds.',
    ],
    gettingStarted:
      'Create your first budget by selecting a category, setting a spending limit, and choosing the budget period. As you record expenses, the budget tracker will update automatically.',
  },
  {
    id: 'reports',
    title: 'Reports',
    icon: BarChart3,
    description:
      'Generate comprehensive financial reports including Profit & Loss, Tax Summary, Cash Flow, and more. Export reports to PDF for sharing with your accountant or filing.',
    features: [
      'Profit & Loss report showing revenue, expenses, and net income over a period.',
      'Tax Summary report with HST/GST collected and paid for easy filing.',
      'Cash Flow report tracking money in and out of your business.',
      'Accounts Summary with a breakdown of all payment accounts.',
      'Accounts Receivable and Accounts Payable aging reports.',
      'Export any report to PDF for printing or sharing.',
    ],
    gettingStarted:
      'Visit the Reports page and select the report type you need. Choose a date range and click "Generate" to view your report. Use the PDF export button to download a copy.',
  },
  {
    id: 'email-scan',
    title: 'Email Scan',
    icon: Inbox,
    description:
      'Connect your Gmail account to automatically scan incoming emails for invoices and receipts. Detected documents are imported into your vault for review and processing.',
    features: [
      'Connect your Gmail account securely via OAuth for email scanning.',
      'Automatic detection of invoice and receipt attachments in incoming emails.',
      'Import detected documents directly into the Documents vault.',
      'Review scanned documents before they are processed or categorized.',
      'Configure scan frequency and filtering rules to control what gets imported.',
    ],
    gettingStarted:
      'Go to Settings and connect your Gmail account under the Gmail integration section. Once connected, navigate to Email Scan to start scanning your inbox for financial documents.',
  },
  {
    id: 'banking',
    title: 'Banking',
    icon: Landmark,
    description:
      'Connect your bank accounts via Plaid to automatically import transactions. Set up auto-categorization rules to streamline your bookkeeping workflow.',
    features: [
      'Connect bank accounts securely through Plaid integration.',
      'Automatic import of bank transactions into the Cashbook.',
      'Create auto-categorization rules to classify transactions by description or amount.',
      'Review and approve imported transactions before they are finalized.',
      'Support for multiple bank accounts and credit cards.',
    ],
    gettingStarted:
      'Navigate to Banking and click "Connect Account" to link your bank via Plaid. Once connected, transactions will be imported automatically and you can set up rules to categorize them.',
  },
  {
    id: 'capture',
    title: 'Capture',
    icon: Camera,
    description:
      'Use the mobile-friendly Capture page to snap photos of receipts on the go. AI extraction automatically reads the receipt details and creates an expense entry for you.',
    features: [
      'Mobile-optimized interface for quick receipt photo capture.',
      'AI-powered extraction reads vendor, amount, date, and tax from receipt images.',
      'Automatically creates an expense entry from the extracted data.',
      'Review and edit extracted details before saving the expense.',
      'Captured images are stored in the Documents vault as attachments.',
    ],
    gettingStarted:
      'Open the Capture page on your phone, take a photo of a receipt, and the AI will extract the details. Review the information, make any corrections, and save to create an expense automatically.',
  },
  {
    id: 'calendar',
    title: 'Calendar',
    icon: Calendar,
    description:
      'The Calendar gives you a visual timeline of your financial activities. View invoice due dates, recurring transaction dates, and budget period boundaries all in one place.',
    features: [
      'Monthly calendar view showing all financial events and deadlines.',
      'Invoice due dates displayed with status color coding (upcoming, overdue).',
      'Recurring transaction dates marked on the calendar for visibility.',
      'Budget period start and end dates for tracking spending windows.',
      'Click any date to see a detailed list of events for that day.',
    ],
    gettingStarted:
      'Visit the Calendar page to see all your upcoming financial dates. Invoices, recurring transactions, and budget periods are displayed automatically based on your existing data.',
  },
  {
    id: 'settings',
    title: 'Settings',
    icon: Settings,
    description:
      'Configure your account and application preferences. Manage users, email templates, integrations, tax rates, payment reminders, and accounting periods.',
    features: [
      'Profile settings for updating your name, email, and password.',
      'User management for adding team members and assigning roles.',
      'Email configuration for outgoing invoice and reminder emails.',
      'Gmail and Banking integration setup (Plaid connection).',
      'Tax rate configuration for HST/GST and other applicable taxes.',
      'Payment reminder schedules, SMS notifications, and accounting period settings.',
    ],
    gettingStarted:
      'Start with the Profile section to ensure your business details are correct, then configure your tax rates under the Tax tab. Connect your email and banking integrations as needed.',
  },
]

export default function HelpPage() {
  const [activeSection, setActiveSection] = useState(sections[0].id)

  const handleNavClick = (id: string) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Help & Documentation</h1>

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
                  Key Features
                </h3>
                <ul className="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 mb-4">
                  {section.features.map((feature, index) => (
                    <li key={index}>{feature}</li>
                  ))}
                </ul>

                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
                  Getting Started
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
