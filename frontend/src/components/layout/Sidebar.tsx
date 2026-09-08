import { useNavigate, useLocation } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  HardDrive,
  Users,
  FileOutput,
  ClipboardList,
  RefreshCw,
  BarChart3,
  HelpCircle,
  LogOut,
  X,
  BookOpen,
  Video,
  Film,
  FileEdit,
  Table2,
  Presentation,
  Sun,
  Moon,
  Languages,
  FileSignature,
  Scale,
  Zap,
  ClipboardCheck,
  Phone,
  Globe,
  Calendar,
  CalendarDays,
  Clock3,
  Contact,
  UserCog,
  ChevronDown,
  ChevronRight,
  MailSearch,
  Mail,
  MessageSquare,
  MessageCircle,
  Kanban,
  ListTodo,
  Settings,
  Lightbulb,
  Trash2,
  ListTree,
  BookText,
  ReceiptText,
  Receipt,
  FileBadge,
  Landmark,
  Wallet,
  Briefcase,
  Building2,
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getTrashCount } from '@/api/cashbook'
import { updateProfile } from '@/api/auth'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useUiStore, type AppMode } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useBranding } from '@/hooks/useBranding'
import { cn, getInitials } from '@/lib/utils'
import { hasFeature } from '@/lib/features'
import type { LucideIcon } from 'lucide-react'
import i18n from '@/i18n'

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  featureKey?: string
}

interface NavSection {
  title: string
  items: NavItem[]
  //: Ledger scope. 'business' sections hide in Personal mode; 'personal'
  //  sections hide in Business mode; undefined = shown in both.
  mode?: AppMode
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: i18n.t('ui:Sidebar.main'),
    items: [
      { path: '/', label: i18n.t('ui:Sidebar.dashboard'), icon: LayoutDashboard },
      { path: '/conversations', label: i18n.t('ui:Sidebar.conversations'), icon: MessageSquare, featureKey: 'inbox' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.crm'),
    items: [
      { path: '/contacts', label: i18n.t('ui:Sidebar.contacts'), icon: Users, featureKey: 'contacts' },
      { path: '/pipelines', label: i18n.t('ui:Sidebar.pipelines'), icon: Kanban, featureKey: 'pipeline' },
      { path: '/tasks', label: i18n.t('ui:Sidebar.tasks'), icon: ListTodo, featureKey: 'tasks' },
      { path: '/business-card', label: i18n.t('ui:Sidebar.businessCard'), icon: Contact, featureKey: 'cards' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.sales'),
    items: [
      { path: '/proposals', label: i18n.t('ui:Sidebar.proposals'), icon: FileSignature, featureKey: 'proposals' },
      { path: '/invoices', label: i18n.t('ui:Sidebar.invoices'), icon: FileOutput, featureKey: 'invoices' },
      { path: '/estimates', label: i18n.t('ui:Sidebar.estimates'), icon: ClipboardList, featureKey: 'estimates' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.personal'),
    mode: 'personal',
    items: [
      { path: '/personal', label: i18n.t('ui:Sidebar.personalFinances'), icon: Wallet },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.accounting'),
    mode: 'business',
    items: [
      { path: '/cashbook', label: i18n.t('ui:Sidebar.cashbook'), icon: BookOpen, featureKey: 'cashbook' },
      { path: '/expenses', label: i18n.t('ui:Sidebar.expenses'), icon: Receipt, featureKey: 'expenses' },
      { path: '/accounting/chart-of-accounts', label: i18n.t('ui:Sidebar.chartOfAccounts'), icon: ListTree, featureKey: 'expenses' },
      { path: '/accounting/journal', label: i18n.t('ui:Sidebar.journal'), icon: BookText, featureKey: 'expenses' },
      { path: '/accounting/bills', label: i18n.t('ui:Sidebar.billsAP'), icon: ReceiptText, featureKey: 'expenses' },
      { path: '/accounting/1099', label: i18n.t('ui:Sidebar.n1099Contractors'), icon: FileBadge, featureKey: 'expenses' },
      { path: '/payroll', label: i18n.t('ui:Sidebar.payroll'), icon: Wallet, featureKey: 'expenses' },
      { path: '/filing', label: i18n.t('ui:Sidebar.taxFiling'), icon: FileBadge, featureKey: 'expenses' },
      { path: '/accounting/ledger-reports', label: i18n.t('ui:Sidebar.financialStatements'), icon: Scale, featureKey: 'expenses' },
      { path: '/cashbook/reconcile', label: i18n.t('ui:Sidebar.reconcile'), icon: Scale, featureKey: 'cashbook' },
      { path: '/smart-import', label: i18n.t('ui:Sidebar.smartImport'), icon: Zap, featureKey: 'smart_import' },
      { path: '/email-scan', label: i18n.t('ui:Sidebar.emailScanner'), icon: MailSearch, featureKey: 'email_scanner' },
      { path: '/bank-transactions', label: i18n.t('ui:Sidebar.bankScanner'), icon: Landmark, featureKey: 'cashbook' },
      { path: '/recurring', label: i18n.t('ui:Sidebar.recurring'), icon: RefreshCw, featureKey: 'recurring' },
      { path: '/reports', label: i18n.t('ui:Sidebar.reports'), icon: BarChart3, featureKey: 'reports' },
      { path: '/cashbook/trash', label: i18n.t('ui:Sidebar.trash'), icon: Trash2, featureKey: 'cashbook' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.communication'),
    items: [
      { path: '/communication?tab=phone-numbers', label: i18n.t('ui:Sidebar.phoneNumbers'), icon: Phone, featureKey: 'phone' },
      { path: '/communication?tab=chat', label: i18n.t('ui:Sidebar.liveChat'), icon: MessageCircle, featureKey: 'sms' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.automation'),
    items: [
      { path: '/workflows', label: i18n.t('ui:Sidebar.workflows'), icon: Zap, featureKey: 'workflows' },
      { path: '/forms', label: i18n.t('ui:Sidebar.forms'), icon: ClipboardCheck, featureKey: 'forms' },
    ],
  },
  {
    title: 'Website',
    items: [
      { path: '/page-builder', label: i18n.t('ui:Sidebar.pages'), icon: Globe, featureKey: 'pages' },
      { path: '/domains', label: 'Domains', icon: Globe, featureKey: 'pages' },
      { path: '/email', label: 'Email', icon: Mail, featureKey: 'pages' },
    ],
  },
  {
    title: 'Documents',
    items: [
      { path: '/docs', label: i18n.t('ui:Sidebar.docs'), icon: FileEdit, featureKey: 'docs' },
      { path: '/sheets', label: i18n.t('ui:Sidebar.sheets'), icon: Table2, featureKey: 'sheets' },
      { path: '/slides', label: i18n.t('ui:Sidebar.slides'), icon: Presentation, featureKey: 'slides' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.storage'),
    items: [
      { path: '/drive', label: i18n.t('ui:Sidebar.drive'), icon: HardDrive, featureKey: 'drive' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.meetings'),
    items: [
      { path: '/calendar', label: i18n.t('ui:Sidebar.calendar'), icon: Calendar, featureKey: 'calendar' },
      { path: '/bookings', label: i18n.t('ui:Sidebar.bookings'), icon: CalendarDays, featureKey: 'calendar' },
      { path: '/availability', label: i18n.t('ui:Sidebar.availability'), icon: Clock3, featureKey: 'calendar' },
      { path: '/meetings', label: i18n.t('ui:Sidebar.meetings_2'), icon: Video, featureKey: 'meeting_rooms' },
      { path: '/recordings', label: i18n.t('ui:Sidebar.recordings'), icon: Film, featureKey: 'meeting_rooms' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.intelligence'),
    items: [
      { path: '/intelligence', label: i18n.t('ui:Sidebar.coachReports'), icon: Lightbulb, featureKey: 'obrain_coach' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.portalManagement'),
    items: [
      { path: '/portal-admin', label: i18n.t('ui:Sidebar.portalAdmin'), icon: UserCog, featureKey: 'portal_admin' },
    ],
  },
  {
    title: i18n.t('ui:Sidebar.admin'),
    items: [
      { path: '/agency', label: i18n.t('ui:Sidebar.clientAccounts'), icon: Building2, featureKey: 'contacts' },
      { path: '/platform-admin', label: i18n.t('ui:Sidebar.platformAdmin'), icon: Settings, featureKey: 'platform_admin' },
    ],
  },
]

export default function Sidebar() {
  const { t } = useTranslation('ui')
  const navigate = useNavigate()
  const location = useLocation()
  const { sidebarOpen, isMobile, panelState, closePanel, theme, toggleTheme, mode, setMode } = useUiStore()
  const { i18n, t: tc } = useTranslation('common')
  const nextLocale = i18n.language === 'fr-CA' ? 'en' : 'fr-CA'
  const { user, logout } = useAuthStore()
  const { logoUrl, orgName } = useBranding()
  const queryClient = useQueryClient()

  const handleSwitchMode = useCallback(async (next: AppMode) => {
    if (next === mode) return
    setMode(next)                    // updates store + localStorage (drives X-App-Mode)
    queryClient.clear()              // financial caches must not cross modes
    try { await updateProfile({ active_mode: next } as any) } catch { /* remembered default is best-effort */ }
    navigate(next === 'personal' ? '/personal' : '/')
  }, [mode, setMode, queryClient, navigate])

  const isItemActive = useCallback((path: string) => {
    const [pathname, query] = path.split('?')
    if (pathname === '/') return location.pathname === '/'
    if (pathname === '/cashbook/reconcile') return location.pathname === '/cashbook/reconcile'
    if (pathname === '/cashbook/trash') return location.pathname === '/cashbook/trash'
    if (pathname === '/cashbook') return location.pathname === '/cashbook' || location.pathname.startsWith('/cashbook/entries') || location.pathname === '/cashbook/new'
    if (query) {
      return location.pathname.startsWith(pathname) && location.search.includes(query)
    }
    return location.pathname.startsWith(pathname)
  }, [location.pathname, location.search])

  const activeSectionIndex = useMemo(() => {
    const idx = NAV_SECTIONS.findIndex((section) =>
      section.items.some((item) => isItemActive(item.path))
    )
    return idx >= 0 ? idx : 0
  }, [isItemActive])

  const [openSection, setOpenSection] = useState(activeSectionIndex)
  const prevActiveSectionRef = useRef(activeSectionIndex)

  // Auto-switch ONLY when navigation changes the active section
  useEffect(() => {
    if (activeSectionIndex !== prevActiveSectionRef.current) {
      setOpenSection(activeSectionIndex)
      prevActiveSectionRef.current = activeSectionIndex
    }
  }, [activeSectionIndex])

  const { data: trashCountData } = useQuery({
    queryKey: ['cashbook-trash-count'],
    queryFn: getTrashCount,
    refetchInterval: 60_000,
    enabled: !!user,
  })
  const trashCount = trashCountData?.data?.total || 0

  if (!sidebarOpen || panelState !== 'sidebar') return null

  const handleNavigate = (path: string) => {
    navigate(path)
    if (isMobile) closePanel()
  }

  const handleToggleSection = (index: number) => {
    setOpenSection(openSection === index ? -1 : index)
  }

  const sidebar = (
    <aside className={cn(
      'w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 min-h-screen flex flex-col',
      isMobile && 'h-screen'
    )}>
      {/* Logo / Org Name */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <button
          onClick={() => handleNavigate('/')}
          className="flex items-center gap-2 min-w-0"
        >
          {logoUrl ? (
            // Commit 31 — sidebar logo at h-20 (80px). Header bar
            // expands to fit; wide wordmarks get up to 220px before
            // letterboxing.
            <img src={logoUrl} alt={orgName} className="h-20 max-w-[220px] object-contain" />
          ) : (
            <span className="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">
              {orgName}
            </span>
          )}
        </button>
        <button
          onClick={closePanel}
          className="p-1 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 shrink-0"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-2 overflow-y-auto scrollbar-thin">
        {NAV_SECTIONS.map((section, index) => {
          // Ledger-scope gate: business sections hide in Personal mode and
          // vice-versa. This is UI convenience; the server-side
          // require_business_mode gate is the real boundary.
          if (section.mode && section.mode !== mode) return null
          // Filter items by feature access
          const visibleItems = section.items.filter(
            item => !item.featureKey || hasFeature(user?.feature_access, item.featureKey)
          )
          if (visibleItems.length === 0) return null
          const isOpen = openSection === index
          return (
            <div key={section.title} className="mb-0.5">
              <button
                onClick={() => handleToggleSection(index)}
                className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] font-semibold tracking-wider text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                {section.title}
                {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
              <div className={cn(
                'overflow-hidden transition-all duration-200 ease-in-out',
                isOpen ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
              )}>
                <div className="space-y-0.5 pb-1">
                  {visibleItems.map((item) => {
                    const Icon = item.icon
                    const active = isItemActive(item.path)
                    return (
                      <button
                        key={item.path}
                        onClick={() => handleNavigate(item.path)}
                        // Commit 26 — active state tints with the brand
                        // primary color via the --brand-primary CSS var
                        // set by BrandThemeProvider. color-mix gives us
                        // a subtle background tint without needing a
                        // pre-baked Tailwind palette per brand.
                        style={active ? {
                          color: 'var(--brand-primary)',
                          backgroundColor: 'color-mix(in srgb, var(--brand-primary) 14%, transparent)',
                        } : undefined}
                        className={cn(
                          'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                          !active && 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100',
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                        {item.path === '/cashbook/trash' && trashCount > 0 && (
                          <span className="ml-auto text-[10px] font-semibold bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                            {trashCount}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="border-t border-gray-100 dark:border-gray-700 p-2 space-y-0.5">
        {/* Business / Personal ledger switch */}
        <div className="flex gap-1 mb-1.5 p-1 rounded-lg bg-gray-100 dark:bg-gray-800">
          <button
            onClick={() => handleSwitchMode('business')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors',
              mode === 'business'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200',
            )}
            title={t('ui:Sidebar.businessBooks')}
          >
            <Briefcase className="h-3.5 w-3.5" /> {t('ui:Sidebar.business')}
          </button>
          <button
            onClick={() => handleSwitchMode('personal')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors',
              mode === 'personal'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200',
            )}
            title={t('ui:Sidebar.personalFinancesPrivateToYou')}
          >
            <Wallet className="h-3.5 w-3.5" /> {t('ui:Sidebar.personal_2')}
          </button>
        </div>

        {/* User info */}
        <div className="flex items-center gap-2.5 px-3 py-2 mb-0.5">
          <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xs font-medium shrink-0">
            {getInitials(user?.full_name)}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{user?.full_name}</p>
            <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">{user?.email}</p>
          </div>
        </div>

        {/* Settings link */}
        <button
          onClick={() => handleNavigate('/settings')}
          style={location.pathname.startsWith('/settings') ? {
            color: 'var(--brand-primary)',
            backgroundColor: 'color-mix(in srgb, var(--brand-primary) 14%, transparent)',
          } : undefined}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            !location.pathname.startsWith('/settings') &&
              'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100',
          )}
        >
          <Settings className="h-4 w-4" /> {t('ui:Sidebar.settings')}
        </button>

        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {theme === 'light' ? <><Moon className="h-4 w-4" /> {t('ui:Sidebar.darkMode')}</> : <><Sun className="h-4 w-4" /> {t('ui:Sidebar.lightMode')}</>}
        </button>
        <button
          // Reload after switching: module-level labels (nav arrays, settings
          // tabs, constants) resolve through i18n.t at import time and would
          // otherwise stay in the old language until the next full load.
          onClick={() => i18n.changeLanguage(nextLocale).then(() => window.location.reload())}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
          aria-label={tc('locale.label')}
          lang={nextLocale}
        >
          <Languages className="h-4 w-4" /> {tc(`locale.${nextLocale}`)}
        </button>
        <button
          onClick={() => handleNavigate('/help')}
          style={location.pathname.startsWith('/help') ? {
            color: 'var(--brand-primary)',
            backgroundColor: 'color-mix(in srgb, var(--brand-primary) 14%, transparent)',
          } : undefined}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            !location.pathname.startsWith('/help') &&
              'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100',
          )}
        >
          <HelpCircle className="h-4 w-4" /> {t('ui:Sidebar.help')}
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-red-600 dark:hover:text-red-400 transition-colors"
        >
          <LogOut className="h-4 w-4" /> {t('ui:Sidebar.logOut')}
        </button>
      </div>
    </aside>
  )

  if (isMobile) {
    return (
      <div className="fixed inset-0 z-50 flex">
        <div className="fixed inset-0 bg-black/40" onClick={closePanel} />
        <div className="relative z-10">{sidebar}</div>
      </div>
    )
  }

  return sidebar
}
