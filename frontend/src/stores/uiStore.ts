import { create } from 'zustand'

function isMobileDevice() {
  return typeof window !== 'undefined' && window.innerWidth < 768
}

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return 'light'
}

interface UiState {
  sidebarOpen: boolean
  isMobile: boolean
  viewMode: 'list' | 'grid'
  theme: 'light' | 'dark'
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setIsMobile: (mobile: boolean) => void
  setViewMode: (mode: 'list' | 'grid') => void
  toggleTheme: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: !isMobileDevice(),
  isMobile: isMobileDevice(),
  viewMode: 'list',
  theme: getInitialTheme(),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setIsMobile: (mobile) => set({ isMobile: mobile }),
  setViewMode: (mode) => set({ viewMode: mode }),
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('theme', next)
      return { theme: next }
    }),
  setTheme: (theme) => {
    localStorage.setItem('theme', theme)
    return set({ theme })
  },
}))
