import { useEffect } from 'react'
import { Link } from 'react-router'
import Header from './Header'
import Sidebar from './Sidebar'
import MobileNav from './MobileNav'
import OBrainPanel from './OBrainPanel'
import { useUiStore } from '@/stores/uiStore'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { isMobile, setIsMobile, panelState, closePanel } = useUiStore()

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (mobile) closePanel()
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [setIsMobile, closePanel])

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950">
      {/* Left sidebar */}
      <Sidebar />

      {/* Center content area */}
      <div className="flex flex-1 flex-col min-w-0">
        <Header />
        <main className={`flex-1 overflow-auto ${isMobile ? 'pb-16' : ''}`}>
          {children}
          <footer className="mt-8 border-t border-gray-200 dark:border-gray-800 px-6 py-3 flex gap-4 text-xs text-gray-400 dark:text-gray-500">
            <Link to="/privacy" className="hover:underline">Privacy Policy</Link>
            <Link to="/terms" className="hover:underline">Terms</Link>
          </footer>
        </main>
      </div>

      {/* Right panel: O-Brain */}
      {panelState === 'obrain' && <OBrainPanel />}

      {/* Mobile bottom nav */}
      <MobileNav />
    </div>
  )
}
