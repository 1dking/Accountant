import { create } from 'zustand'

function isMobileDevice() {
  return typeof window !== 'undefined' && window.innerWidth < 768
}

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'dark'
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return 'dark'
}

export type AppMode = 'business' | 'personal'

// The active ledger. localStorage key 'app_mode' is ALSO read by the API client
// (src/api/client.ts) which sends it as the X-App-Mode header on every request,
// so this store and the header always agree.
function getInitialMode(): AppMode {
  if (typeof window === 'undefined') return 'business'
  return localStorage.getItem('app_mode') === 'personal' ? 'personal' : 'business'
}

export type PanelState = 'sidebar' | 'obrain' | 'neither'

interface UiState {
  sidebarOpen: boolean
  isMobile: boolean
  viewMode: 'list' | 'grid'
  theme: 'light' | 'dark'
  mode: AppMode
  panelState: PanelState
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setIsMobile: (mobile: boolean) => void
  setViewMode: (mode: 'list' | 'grid') => void
  toggleTheme: () => void
  setTheme: (theme: 'light' | 'dark') => void
  setMode: (mode: AppMode) => void
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
  mode: getInitialMode(),
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
  setMode: (mode) => {
    localStorage.setItem('app_mode', mode)
    return set({ mode })
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
