import { useNavigate, useLocation } from 'react-router'
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
  FileSignature,
  Scale,
  Zap,
  ClipboardCheck,
  Phone,
  Globe,
  Calendar,
  CalendarDays,
  UserCog,
  ChevronDown,
  ChevronRight,
  MailSearch,
  MessageSquare,
  MessageCircle,
  Kanban,
  Settings,
  Lightbulb,
} from 'lucide-react'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useBranding } from '@/hooks/useBranding'
import { cn, getInitials } from '@/lib/utils'
import { hasFeature } from '@/lib/features'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  featureKey?: string
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
      { path: '/conversations', label: 'Conversations', icon: MessageSquare, featureKey: 'inbox' },
    ],
  },
  {
    title: 'CRM',
    items: [
      { path: '/contacts', label: 'Contacts', icon: Users, featureKey: 'contacts' },
      { path: '/pipelines', label: 'Pipelines', icon: Kanban, featureKey: 'pipeline' },
    ],
  },
  {
    title: 'SALES',
    items: [
      { path: '/proposals', label: 'Proposals', icon: FileSignature, featureKey: 'proposals' },
      { path: '/invoices', label: 'Invoices', icon: FileOutput, featureKey: 'invoices' },
      { path: '/estimates', label: 'Estimates', icon: ClipboardList, featureKey: 'invoices' },
    ],
  },
  {
    title: 'ACCOUNTING',
    items: [
      { path: '/cashbook', label: 'Cashbook', icon: BookOpen, featureKey: 'cashbook' },
      { path: '/cashbook/reconcile', label: 'Reconcile', icon: Scale, featureKey: 'cashbook' },
      { path: '/smart-import', label: 'Smart Import', icon: Zap, featureKey: 'smart_import' },
      { path: '/email-scan', label: 'Email Scanner', icon: MailSearch, featureKey: 'email_scanner' },
      { path: '/recurring', label: 'Recurring', icon: RefreshCw, featureKey: 'recurring' },
      { path: '/reports', label: 'Reports', icon: BarChart3, featureKey: 'reports' },
    ],
  },
  {
    title: 'COMMUNICATION',
    items: [
      { path: '/communication?tab=phone-numbers', label: 'Phone Numbers', icon: Phone, featureKey: 'phone' },
      { path: '/communication?tab=chat', label: 'Live Chat', icon: MessageCircle, featureKey: 'sms' },
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
      { path: '/page-builder', label: 'Pages', icon: Globe, featureKey: 'pages' },
      { path: '/docs', label: 'Docs', icon: FileEdit, featureKey: 'docs' },
      { path: '/sheets', label: 'Sheets', icon: Table2, featureKey: 'sheets' },
      { path: '/slides', label: 'Slides', icon: Presentation, featureKey: 'slides' },
    ],
  },
  {
    title: 'STORAGE',
    items: [
      { path: '/drive', label: 'Drive', icon: HardDrive, featureKey: 'drive' },
    ],
  },
  {
    title: 'MEETINGS',
    items: [
      { path: '/calendar', label: 'Calendar', icon: Calendar, featureKey: 'calendar' },
      { path: '/meetings', label: 'Meetings', icon: Video, featureKey: 'meeting_rooms' },
      { path: '/recordings', label: 'Recordings', icon: Film, featureKey: 'meeting_rooms' },
      { path: '/scheduling', label: 'Scheduling', icon: CalendarDays, featureKey: 'calendar' },
    ],
  },
  {
    title: 'INTELLIGENCE',
    items: [
      { path: '/intelligence', label: 'Coach Reports', icon: Lightbulb, featureKey: 'obrain_coach' },
    ],
  },
  {
    title: 'PORTAL MANAGEMENT',
    items: [
      { path: '/portal-admin', label: 'Portal Admin', icon: UserCog, featureKey: 'portal_admin' },
    ],
  },
  {
    title: 'ADMIN',
    items: [
      { path: '/platform-admin', label: 'Platform Admin', icon: Settings, featureKey: 'platform_admin' },
    ],
  },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { sidebarOpen, isMobile, panelState, closePanel, theme, toggleTheme } = useUiStore()
  const { user, logout } = useAuthStore()
  const { logoUrl, orgName } = useBranding()

  const isItemActive = useCallback((path: string) => {
    const [pathname, query] = path.split('?')
    if (pathname === '/') return location.pathname === '/'
    if (pathname === '/cashbook/reconcile') return location.pathname === '/cashbook/reconcile'
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
            <img src={logoUrl} alt={orgName} className="h-7 max-w-[140px] object-contain" />
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
              </div>
            </div>
          )
        })}
      </nav>

      {/* Bottom */}
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

        {/* Settings link */}
        <button
          onClick={() => handleNavigate('/settings')}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            location.pathname.startsWith('/settings')
              ? 'bg-blue-50/70 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
          )}
        >
          <Settings className="h-4 w-4" /> Settings
        </button>

        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100"
        >
          {theme === 'light' ? <><Moon className="h-4 w-4" /> Dark mode</> : <><Sun className="h-4 w-4" /> Light mode</>}
        </button>
        <button
          onClick={() => handleNavigate('/help')}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            location.pathname.startsWith('/help')
              ? 'bg-blue-50/70 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
          )}
        >
          <HelpCircle className="h-4 w-4" /> Help
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-red-600 dark:hover:text-red-400 transition-colors"
        >
          <LogOut className="h-4 w-4" /> Log out
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
