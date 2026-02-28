import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ErrorBoundary from '@/components/ErrorBoundary'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { wsClient } from '@/api/websocket'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
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
import MeetingGuestJoinPage from '@/pages/MeetingGuestJoinPage'
import RecordingsPage from '@/pages/RecordingsPage'
import HelpPage from '@/pages/HelpPage'
import DocsHomePage from '@/pages/DocsHomePage'
import SheetsHomePage from '@/pages/SheetsHomePage'
import SlidesHomePage from '@/pages/SlidesHomePage'
import DocEditorPage from '@/pages/DocEditorPage'
import SheetEditorPage from '@/pages/SheetEditorPage'
import SlideEditorPage from '@/pages/SlideEditorPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

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

  return <>{children}</>
}

function AuthenticatedApp() {
  const { isAuthenticated } = useAuthStore()
  const { fetchNotifications, addNotification } = useNotificationStore()

  useEffect(() => {
    if (isAuthenticated) {
      wsClient.connect()
      fetchNotifications()

      const unsub = wsClient.on('notification.new', (event) => {
        addNotification(event.data as any)
      })

      return () => {
        unsub()
        wsClient.disconnect()
      }
    }
  }, [isAuthenticated, fetchNotifications, addNotification])

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/drive" element={<DrivePage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/contacts/new" element={<NewContactPage />} />
        <Route path="/contacts/:id" element={<ContactDetailPage />} />
        <Route path="/cashbook" element={<CashbookPage />} />
        <Route path="/cashbook/new" element={<NewCashbookEntryPage />} />
        <Route path="/cashbook/entries/:id" element={<CashbookEntryDetailPage />} />
        <Route path="/expenses" element={<ExpensesPage />} />
        <Route path="/expenses/new" element={<NewExpensePage />} />
        <Route path="/expenses/dashboard" element={<ExpenseDashboardPage />} />
        <Route path="/expenses/:id" element={<ExpenseDetailPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/invoices/new" element={<NewInvoicePage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
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
        <Route path="/email-scan" element={<EmailScanPage />} />
        <Route path="/bank-transactions" element={<BankTransactionsPage />} />
        <Route path="/capture" element={<CapturePage />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/meetings/new" element={<NewMeetingPage />} />
        <Route path="/meetings/:id" element={<MeetingDetailPage />} />
        <Route path="/meetings/:id/room" element={<MeetingRoomPage />} />
        <Route path="/recordings" element={<RecordingsPage />} />
        <Route path="/docs" element={<DocsHomePage />} />
        <Route path="/docs/:id" element={<DocEditorPage />} />
        <Route path="/sheets" element={<SheetsHomePage />} />
        <Route path="/sheets/:id" element={<SheetEditorPage />} />
        <Route path="/slides" element={<SlidesHomePage />} />
        <Route path="/slides/:id" element={<SlideEditorPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  const { initialize } = useAuthStore()

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/meetings/:id/guest" element={<MeetingGuestJoinPage />} />
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
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
