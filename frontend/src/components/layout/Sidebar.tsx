import { useNavigate, useLocation } from 'react-router'
import {
  LayoutDashboard,
  FileText,
  HardDrive,
  Users,
  FileOutput,
  ClipboardList,
  Receipt,
  TrendingUp,
  RefreshCw,
  PiggyBank,
  BarChart3,
  Camera,
  Calendar,
  Settings,
  HelpCircle,
  LogOut,
  X,
  Inbox,
  Landmark,
  BookOpen,
  Video,
  Film,
  FileEdit,
  Table2,
  Presentation,
  Sun,
  Moon,
  FileSignature,
  Scale,
  Zap,
  ClipboardCheck,
  Phone,
  Globe,
  CalendarDays,
  Palette,
  UserCog,
  ChevronDown,
  ChevronRight,
  MailSearch,
} from 'lucide-react'
import { useState, useMemo } from 'react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { cn, getInitials } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

interface NavSection {
  title: string
  items: NavItem[]
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: 'MAIN',
    items: [
      { path: '/', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/calendar', label: 'Calendar', icon: Calendar },
      { path: '/capture', label: 'Capture', icon: Camera },
    ],
  },
  {
    title: 'CRM',
    items: [
      { path: '/contacts', label: 'Contacts', icon: Users },
    ],
  },
  {
    title: 'SALES',
    items: [
      { path: '/invoices', label: 'Invoices', icon: FileOutput },
      { path: '/proposals', label: 'Proposals', icon: FileSignature },
      { path: '/estimates', label: 'Estimates', icon: ClipboardList },
    ],
  },
  {
    title: 'ACCOUNTING',
    items: [
      { path: '/cashbook', label: 'Cashbook', icon: BookOpen },
      { path: '/cashbook/reconcile', label: 'Reconcile', icon: Scale },
      { path: '/expenses', label: 'Expenses', icon: Receipt },
      { path: '/income', label: 'Income', icon: TrendingUp },
      { path: '/recurring', label: 'Recurring', icon: RefreshCw },
      { path: '/budgets', label: 'Budgets', icon: PiggyBank },
      { path: '/bank-transactions', label: 'Banking', icon: Landmark },
      { path: '/email-scan', label: 'Email Scanner', icon: MailSearch },
      { path: '/reports', label: 'Reports', icon: BarChart3 },
    ],
  },
  {
    title: 'COMMUNICATION',
    items: [
      { path: '/inbox', label: 'Inbox', icon: Inbox },
      { path: '/communication', label: 'Dialer & SMS', icon: Phone },
    ],
  },
  {
    title: 'AUTOMATION',
    items: [
      { path: '/workflows', label: 'Workflows', icon: Zap },
      { path: '/forms', label: 'Forms', icon: ClipboardCheck },
    ],
  },
  {
    title: 'CONTENT',
    items: [
      { path: '/page-builder', label: 'Pages', icon: Globe },
      { path: '/documents', label: 'Documents', icon: FileText },
      { path: '/docs', label: 'Docs', icon: FileEdit },
      { path: '/sheets', label: 'Sheets', icon: Table2 },
      { path: '/slides', label: 'Slides', icon: Presentation },
    ],
  },
  {
    title: 'STORAGE',
    items: [
      { path: '/drive', label: 'Drive', icon: HardDrive },
    ],
  },
  {
    title: 'MEETINGS',
    items: [
      { path: '/meetings', label: 'Meetings', icon: Video },
      { path: '/recordings', label: 'Recordings', icon: Film },
      { path: '/scheduling', label: 'Scheduling', icon: CalendarDays },
    ],
  },
  {
    title: 'PORTAL MANAGEMENT',
    items: [
      { path: '/portal-admin', label: 'Portal Admin', icon: UserCog },
      { path: '/branding', label: 'Branding', icon: Palette },
    ],
  },
  {
    title: 'SETTINGS',
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { sidebarOpen, isMobile, setSidebarOpen, theme, toggleTheme } = useUiStore()
  const { user, logout } = useAuthStore()

  const isItemActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    if (path === '/cashbook/reconcile') return location.pathname === '/cashbook/reconcile'
    if (path === '/cashbook') return location.pathname === '/cashbook' || location.pathname.startsWith('/cashbook/entries') || location.pathname === '/cashbook/new'
    return location.pathname.startsWith(path)
  }

  // Determine which section contains the active page
  const activeSectionIndex = useMemo(() => {
    const idx = NAV_SECTIONS.findIndex((section) =>
      section.items.some((item) => isItemActive(item.path))
    )
    return idx >= 0 ? idx : 0
  }, [location.pathname])

  // Accordion state: only one section open at a time
  const [openSection, setOpenSection] = useState(activeSectionIndex)

  // When the active page changes to a different section, auto-switch
  if (openSection !== activeSectionIndex && NAV_SECTIONS[activeSectionIndex]?.items.some((item) => isItemActive(item.path))) {
    setOpenSection(activeSectionIndex)
  }

  if (!sidebarOpen) return null

  const handleNavigate = (path: string) => {
    navigate(path)
    if (isMobile) setSidebarOpen(false)
  }

  const handleToggleSection = (index: number) => {
    setOpenSection(openSection === index ? -1 : index)
  }

  const sidebar = (
    <aside className={cn(
      'w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 min-h-screen flex flex-col',
      isMobile && 'h-screen'
    )}>
      {/* Logo */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <h1
          className="text-lg font-bold text-gray-900 dark:text-gray-100 cursor-pointer"
          onClick={() => handleNavigate('/')}
        >
          Accountant
        </h1>
        {isMobile && (
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-2 overflow-y-auto scrollbar-thin">
        {NAV_SECTIONS.map((section, index) => {
          const isOpen = openSection === index
          return (
            <div key={section.title} className="mb-1">
              <button
                onClick={() => handleToggleSection(index)}
                className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] font-semibold tracking-wider text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                {section.title}
                {isOpen ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>
              {isOpen && (
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon
                    const active = isItemActive(item.path)
                    return (
                      <button
                        key={item.path}
                        onClick={() => handleNavigate(item.path)}
                        className={cn(
                          'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                          active
                            ? 'bg-blue-50/70 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-gray-100 dark:border-gray-700 p-2 space-y-0.5">
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

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {theme === 'light' ? (
            <>
              <Moon className="h-4 w-4" />
              Dark mode
            </>
          ) : (
            <>
              <Sun className="h-4 w-4" />
              Light mode
            </>
          )}
        </button>

        {/* Help */}
        <button
          onClick={() => handleNavigate('/help')}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            location.pathname.startsWith('/help')
              ? 'bg-blue-50/70 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
          )}
        >
          <HelpCircle className="h-4 w-4" />
          Help
        </button>

        {/* Logout */}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-red-600 dark:hover:text-red-400 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  )

  // On mobile, render as a fixed overlay with backdrop
  if (isMobile) {
    return (
      <div className="fixed inset-0 z-50 flex">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/40"
          onClick={() => setSidebarOpen(false)}
        />
        {/* Sidebar panel */}
        <div className="relative z-10">
          {sidebar}
        </div>
      </div>
    )
  }

  return sidebar
}
