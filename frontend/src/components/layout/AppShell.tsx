import { useEffect } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'
import MobileNav from './MobileNav'
import { useUiStore } from '@/stores/uiStore'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { isMobile, setIsMobile, setSidebarOpen } = useUiStore()

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (mobile) setSidebarOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [setIsMobile, setSidebarOpen])

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <Header />
        <main className={`flex-1 overflow-auto ${isMobile ? 'pb-16' : ''}`}>
          {children}
        </main>
      </div>
      <MobileNav />
    </div>
  )
}
