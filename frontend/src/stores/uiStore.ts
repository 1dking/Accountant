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

export type PanelState = 'sidebar' | 'obrain' | 'neither'

interface UiState {
  sidebarOpen: boolean
  isMobile: boolean
  viewMode: 'list' | 'grid'
  theme: 'light' | 'dark'
  panelState: PanelState
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setIsMobile: (mobile: boolean) => void
  setViewMode: (mode: 'list' | 'grid') => void
  toggleTheme: () => void
  setTheme: (theme: 'light' | 'dark') => void
  setPanelState: (state: PanelState) => void
  openSidebar: () => void
  openOBrain: () => void
  closePanel: () => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: !isMobileDevice(),
  isMobile: isMobileDevice(),
  viewMode: 'list',
  theme: getInitialTheme(),
  panelState: isMobileDevice() ? 'neither' : 'sidebar',
  toggleSidebar: () =>
    set((s) => {
      const newOpen = !s.sidebarOpen
      return {
        sidebarOpen: newOpen,
        panelState: newOpen ? 'sidebar' : 'neither',
      }
    }),
  setSidebarOpen: (open) =>
    set({
      sidebarOpen: open,
      panelState: open ? 'sidebar' : 'neither',
    }),
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
  setPanelState: (state) =>
    set({
      panelState: state,
      sidebarOpen: state === 'sidebar',
    }),
  openSidebar: () =>
    set({
      panelState: 'sidebar',
      sidebarOpen: true,
    }),
  openOBrain: () =>
    set({
      panelState: 'obrain',
      sidebarOpen: false,
    }),
  closePanel: () =>
    set({
      panelState: 'neither',
      sidebarOpen: false,
    }),
}))
