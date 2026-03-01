import { useNavigate, useLocation } from 'react-router'
import { LayoutDashboard, FileText, Camera, Receipt, Menu } from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

import type { LucideIcon } from 'lucide-react'

interface MobileTab {
  path: string
  label: string
  icon: LucideIcon
  highlight?: boolean
}

const MOBILE_TABS: MobileTab[] = [
  { path: '/', label: 'Home', icon: LayoutDashboard },
  { path: '/documents', label: 'Docs', icon: FileText },
  { path: '/capture', label: 'Capture', icon: Camera, highlight: true },
  { path: '/expenses', label: 'Expenses', icon: Receipt },
  { path: '/_menu', label: 'More', icon: Menu },
]

export default function MobileNav() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isMobile, setSidebarOpen } = useUiStore()

  if (!isMobile) return null

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 safe-area-pb">
      <div className="flex items-center justify-around h-14">
        {MOBILE_TABS.map((tab) => {
          const Icon = tab.icon
          const isMenu = tab.path === '/_menu'
          const isActive = isMenu
            ? false
            : tab.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(tab.path)

          const handleClick = () => {
            if (isMenu) {
              setSidebarOpen(true)
            } else {
              navigate(tab.path)
            }
          }

          if (tab.highlight) {
            return (
              <button
                key={tab.path}
                onClick={handleClick}
                className="flex flex-col items-center justify-center -mt-4"
              >
                <div className="h-12 w-12 rounded-full bg-blue-600 flex items-center justify-center shadow-lg">
                  <Icon className="h-6 w-6 text-white" />
                </div>
                <span className="text-[10px] font-medium text-blue-600 dark:text-blue-400 mt-0.5">{tab.label}</span>
              </button>
            )
          }

          return (
            <button
              key={tab.path}
              onClick={handleClick}
              className="flex flex-col items-center justify-center gap-0.5 min-w-[56px]"
            >
              <Icon
                className={cn(
                  'h-5 w-5',
                  isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'
                )}
              />
              <span
                className={cn(
                  'text-[10px] font-medium',
                  isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'
                )}
              >
                {tab.label}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
