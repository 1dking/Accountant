import { useNavigate, useLocation } from 'react-router'
import {
  LayoutDashboard,
  FileText,
  Users,
  FileOutput,
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
} from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { cn, getInitials } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Home', icon: LayoutDashboard },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/contacts', label: 'Contacts', icon: Users },
  { path: '/invoices', label: 'Invoices', icon: FileOutput },
  { path: '/expenses', label: 'Expenses', icon: Receipt },
  { path: '/income', label: 'Income', icon: TrendingUp },
  { path: '/recurring', label: 'Recurring', icon: RefreshCw },
  { path: '/budgets', label: 'Budgets', icon: PiggyBank },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { path: '/email-scan', label: 'Inbox', icon: Inbox },
  { path: '/bank-transactions', label: 'Banking', icon: Landmark },
  { path: '/capture', label: 'Capture', icon: Camera },
  { path: '/calendar', label: 'Calendar', icon: Calendar },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { sidebarOpen, isMobile, setSidebarOpen } = useUiStore()
  const { user, logout } = useAuthStore()

  if (!sidebarOpen) return null

  const handleNavigate = (path: string) => {
    navigate(path)
    if (isMobile) setSidebarOpen(false)
  }

  const sidebar = (
    <aside className={cn(
      'w-60 bg-white border-r border-gray-200 min-h-screen flex flex-col',
      isMobile && 'h-screen'
    )}>
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <h1
          className="text-lg font-bold text-gray-900 cursor-pointer"
          onClick={() => handleNavigate('/')}
        >
          Accountant
        </h1>
        {isMobile && (
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive =
            item.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.path)
          return (
            <button
              key={item.path}
              onClick={() => handleNavigate(item.path)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-50/70 text-blue-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-gray-100 p-3 space-y-1">
        {/* User info */}
        <div className="flex items-center gap-3 px-3 py-2 mb-1">
          <div className="h-9 w-9 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-medium shrink-0">
            {getInitials(user?.full_name)}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name}</p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>
        </div>

        {/* Help */}
        <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors">
          <HelpCircle className="h-5 w-5" />
          Help & information
        </button>

        {/* Logout */}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="h-5 w-5" />
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
