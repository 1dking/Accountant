import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router'
import { FEATURE_LABELS, featureForPath, hasFeature } from '@/lib/features'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import ErrorBoundary from '@/components/ErrorBoundary'
import BrandThemeProvider from '@/components/BrandThemeProvider'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useUiStore } from '@/stores/uiStore'
import { wsClient } from '@/api/websocket'
import { useBranding } from '@/hooks/useBranding'
import AppShell from '@/components/layout/AppShell'
import InstallBanner from '@/components/layout/InstallBanner'
import LoginPage from '@/pages/LoginPage'
import SalesPage from '@/pages/SalesPage'
import DashboardPage from '@/pages/DashboardPage'
import AdminTeamPage from '@/pages/AdminTeamPage'
import DocumentsPage from '@/pages/DocumentsPage'
import DocumentDetailPage from '@/pages/DocumentDetailPage'
import CalendarPage from '@/pages/CalendarPage'
import SettingsPage from '@/pages/SettingsPage'
import ExpensesPage from '@/pages/ExpensesPage'
import ExpenseDetailPage from '@/pages/ExpenseDetailPage'
import NewExpensePage from '@/pages/NewExpensePage'
import ExpenseDashboardPage from '@/pages/ExpenseDashboardPage'
import ContactsPage from '@/pages/ContactsPage'
import ContactDetailPage from '@/pages/ContactDetailPage'
import NewContactPage from '@/pages/NewContactPage'
import InvoicesPage from '@/pages/InvoicesPage'
import InvoiceDetailPage from '@/pages/InvoiceDetailPage'
import NewInvoicePage from '@/pages/NewInvoicePage'
import IncomePage from '@/pages/IncomePage'
import NewIncomePage from '@/pages/NewIncomePage'
import RecurringPage from '@/pages/RecurringPage'
import NewRecurringRulePage from '@/pages/NewRecurringRulePage'
import BudgetsPage from '@/pages/BudgetsPage'
import NewBudgetPage from '@/pages/NewBudgetPage'
import ReportsPage from '@/pages/ReportsPage'
import CapturePage from '@/pages/CapturePage'
import EmailScanPage from '@/pages/EmailScanPage'
import BankTransactionsPage from '@/pages/BankTransactionsPage'
import EstimatesPage from '@/pages/EstimatesPage'
import NewEstimatePage from '@/pages/NewEstimatePage'
import EstimateDetailPage from '@/pages/EstimateDetailPage'
import CashbookPage from '@/pages/CashbookPage'
import NewCashbookEntryPage from '@/pages/NewCashbookEntryPage'
import CashbookEntryDetailPage from '@/pages/CashbookEntryDetailPage'
import DrivePage from '@/pages/DrivePage'
import MeetingsPage from '@/pages/MeetingsPage'
import NewMeetingPage from '@/pages/NewMeetingPage'
import MeetingDetailPage from '@/pages/MeetingDetailPage'
import MeetingRoomPage from '@/pages/MeetingRoomPage'
import MeetingJoinPage from '@/pages/MeetingJoinPage'
import MeetingGuestJoinPage from '@/pages/MeetingGuestJoinPage'
import RecordingsPage from '@/pages/RecordingsPage'
import GoogleCallbackPage from '@/pages/GoogleCallbackPage'
import PasswordResetRequestPage from '@/pages/PasswordResetRequestPage'
import PasswordResetConfirmPage from '@/pages/PasswordResetConfirmPage'
import HelpPage from '@/pages/HelpPage'
import PublicDocumentPage from '@/pages/PublicDocumentPage'
import PublicFormPage from '@/pages/PublicFormPage'
import DocsHomePage from '@/pages/DocsHomePage'
import SheetsHomePage from '@/pages/SheetsHomePage'
import SlidesHomePage from '@/pages/SlidesHomePage'
import DocEditorPage from '@/pages/DocEditorPage'
import DocReaderPage from '@/pages/DocReaderPage'
import SheetEditorPage from '@/pages/SheetEditorPage'
import SlideEditorPage from '@/pages/SlideEditorPage'
import ProposalsPage from '@/pages/ProposalsPage'
import ProposalEditorPage from '@/pages/ProposalEditorPage'
import ProposalSigningPage from '@/pages/ProposalSigningPage'
import ProposalPaymentRedirectPage from '@/pages/ProposalPaymentRedirectPage'
import ReconciliationPage from '@/pages/ReconciliationPage'
import InboxPage from '@/pages/InboxPage'
import PortalDashboardPage from '@/pages/PortalDashboardPage'
import PortalInvoicesPage from '@/pages/PortalInvoicesPage'
import PortalProposalsPage from '@/pages/PortalProposalsPage'
import PortalFilesPage from '@/pages/PortalFilesPage'
import PortalMeetingsPage from '@/pages/PortalMeetingsPage'
import WorkflowsPage from '@/pages/WorkflowsPage'
import FormsPage from '@/pages/FormsPage'
import CommunicationPage from '@/pages/CommunicationPage'
import PageBuilderPage from '@/pages/PageBuilderPage'
import AvailabilityPage from '@/pages/AvailabilityPage'
import BookingsPage from '@/pages/BookingsPage'
import PublicBookingPage from '@/pages/PublicBookingPage'
import BrandingPage from '@/pages/BrandingPage'
import PortalAdminPage from '@/pages/PortalAdminPage'
import PipelinesPage from '@/pages/PipelinesPage'
import ConversationsPage from '@/pages/ConversationsPage'
import OBrainPage from '@/pages/OBrainPage'
import SmartImportPage from '@/pages/SmartImportPage'
import TrashPage from '@/pages/TrashPage'
import PlatformAdminPage from '@/pages/PlatformAdminPage'
import IntelligencePage from '@/pages/IntelligencePage'
import ReschedulePage from '@/pages/ReschedulePage'
import CancelBookingPage from '@/pages/CancelBookingPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function RootGate() {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <SalesPage />
  }

  return (
    <ProtectedRoute>
      <AuthenticatedApp />
    </ProtectedRoute>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuthStore()
  const location = useLocation()

  // Must come before any feature check: hasFeature fails closed, so evaluating
  // it mid-load would bounce the user off their own page on every refresh.
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Module gate. Hiding a sidebar link never stopped anyone typing /cashbook
  // into the address bar — every route here was reachable that way. One choke
  // point, so a new route is guarded by default rather than silently open.
  const feature = featureForPath(location.pathname)
  if (feature && !hasFeature(user?.feature_access, feature)) {
    return <ModuleNotEnabled feature={feature} />
  }

  return <>{children}</>
}

function ModuleNotEnabled({ feature }: { feature: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          {FEATURE_LABELS[feature] ?? feature} isn&apos;t enabled for your account
        </h1>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Ask an admin to switch this section on for you.
        </p>
        <Link
          to="/"
          className="inline-block mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}

function AuthenticatedApp() {
  const { isAuthenticated } = useAuthStore()
  const { fetchNotifications, addNotification } = useNotificationStore()
  const { orgName } = useBranding()

  // Set browser tab title from branding
  useEffect(() => {
    document.title = orgName
  }, [orgName])

  useEffect(() => {
    if (isAuthenticated) {
      wsClient.connect()
      fetchNotifications()

      // Backend publishes type='notification' (not 'notification.new').
      const unsubNotif = wsClient.on('notification', (event) => {
        addNotification(event.data as any)
      })

      // sms.received fans out to any tab subscribed to a contact thread.
      // The thread component (ContactConversationThread) reads
      // event.data.contact_id and refetches its query if it matches.
      // Nothing to do here at the App level — listener lives in the
      // thread component.

      return () => {
        unsubNotif()
        wsClient.disconnect()
      }
    }
  }, [isAuthenticated, fetchNotifications, addNotification])

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/admin/team" element={<AdminTeamPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/drive" element={<DrivePage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/contacts/new" element={<NewContactPage />} />
        <Route path="/contacts/:id" element={<ContactDetailPage />} />
        <Route path="/cashbook" element={<CashbookPage />} />
        <Route path="/cashbook/new" element={<NewCashbookEntryPage />} />
        <Route path="/cashbook/entries/:id" element={<CashbookEntryDetailPage />} />
        <Route path="/cashbook/reconcile" element={<ReconciliationPage />} />
        <Route path="/cashbook/trash" element={<TrashPage />} />
        <Route path="/expenses" element={<ExpensesPage />} />
        <Route path="/expenses/new" element={<NewExpensePage />} />
        <Route path="/expenses/dashboard" element={<ExpenseDashboardPage />} />
        <Route path="/expenses/:id" element={<ExpenseDetailPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/invoices/new" element={<NewInvoicePage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="/proposals" element={<ProposalsPage />} />
        <Route path="/proposals/:id/edit" element={<ProposalEditorPage />} />
        <Route path="/proposals/:id" element={<ProposalEditorPage />} />
        <Route path="/estimates" element={<EstimatesPage />} />
        <Route path="/estimates/new" element={<NewEstimatePage />} />
        <Route path="/estimates/:id" element={<EstimateDetailPage />} />
        <Route path="/income" element={<IncomePage />} />
        <Route path="/income/new" element={<NewIncomePage />} />
        <Route path="/recurring" element={<RecurringPage />} />
        <Route path="/recurring/new" element={<NewRecurringRulePage />} />
        <Route path="/budgets" element={<BudgetsPage />} />
        <Route path="/budgets/new" element={<NewBudgetPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/pipelines" element={<PipelinesPage />} />
        <Route path="/email-scan" element={<EmailScanPage />} />
        <Route path="/smart-import" element={<SmartImportPage />} />
        <Route path="/bank-transactions" element={<BankTransactionsPage />} />
        <Route path="/capture" element={<CapturePage />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/meetings/new" element={<NewMeetingPage />} />
        <Route path="/meetings/:id" element={<MeetingDetailPage />} />
        {/* MeetingRoomPage rendered outside AppShell — see top-level routes */}
        <Route path="/recordings" element={<RecordingsPage />} />
        <Route path="/docs" element={<DocsHomePage />} />
        <Route path="/docs/:id" element={<DocEditorPage />} />
        <Route path="/docs/:id/read" element={<DocReaderPage />} />
        <Route path="/sheets" element={<SheetsHomePage />} />
        <Route path="/sheets/:id" element={<SheetEditorPage />} />
        <Route path="/slides" element={<SlidesHomePage />} />
        <Route path="/slides/:id" element={<SlideEditorPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/forms" element={<FormsPage />} />
        <Route path="/communication" element={<CommunicationPage />} />
        <Route path="/page-builder" element={<PageBuilderPage />} />
        <Route path="/availability" element={<AvailabilityPage />} />
        <Route path="/bookings" element={<BookingsPage />} />
        {/* The old combined Scheduling page was split into Availability +
            Bookings (Arivio-style) — keep old bookmarks working. */}
        <Route path="/scheduling" element={<Navigate to="/availability" replace />} />
        <Route path="/branding" element={<BrandingPage />} />
        <Route path="/portal-admin" element={<PortalAdminPage />} />
        <Route path="/platform-admin" element={<PlatformAdminPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  const { initialize } = useAuthStore()
  const theme = useUiStore((s) => s.theme)

  useEffect(() => {
    initialize()
  }, [initialize])

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrandThemeProvider>
        <Toaster position="bottom-right" richColors closeButton />
        <InstallBanner />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/password-reset/request" element={<PasswordResetRequestPage />} />
            <Route path="/auth/password-reset/confirm/:token" element={<PasswordResetConfirmPage />} />
            <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />
            <Route path="/p/:token" element={<PublicDocumentPage />} />
            <Route path="/f/:formId" element={<PublicFormPage />} />
            <Route path="/proposals/sign/:token" element={<ProposalSigningPage />} />
            <Route path="/proposals/:id/payment" element={<ProposalPaymentRedirectPage />} />
            <Route path="/meetings/:id/guest" element={<MeetingGuestJoinPage />} />
            {/* Commit 8 — Google-Meet-style public meeting URL.
                Guests land here, enter name + email, knock the lobby. */}
            <Route path="/m/:slug" element={<MeetingJoinPage />} />
            {/* Public booking */}
            <Route path="/book/:slug" element={<PublicBookingPage />} />
            <Route path="/booking/reschedule/:token" element={<ReschedulePage />} />
            <Route path="/booking/cancel/:token" element={<CancelBookingPage />} />
            {/* Portal routes */}
            <Route path="/portal" element={<PortalDashboardPage />} />
            <Route path="/portal/invoices" element={<PortalInvoicesPage />} />
            <Route path="/portal/proposals" element={<PortalProposalsPage />} />
            <Route path="/portal/files" element={<PortalFilesPage />} />
            <Route path="/portal/meetings" element={<PortalMeetingsPage />} />
            <Route
              path="/meetings/:id/room"
              element={
                <ProtectedRoute>
                  <MeetingRoomPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/brain"
              element={
                <ProtectedRoute>
                  <OBrainPage />
                </ProtectedRoute>
              }
            />
            {/* The front door. A logged-out visitor to the root gets the sales
                page (there used to be nothing here — straight redirect to
                /login); a logged-in user still lands on their dashboard. */}
            <Route path="/" element={<RootGate />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <AuthenticatedApp />
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
        </BrandThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
