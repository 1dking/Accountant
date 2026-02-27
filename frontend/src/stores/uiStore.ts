import { create } from 'zustand'

function isMobileDevice() {
  return typeof window !== 'undefined' && window.innerWidth < 768
}

interface UiState {
  sidebarOpen: boolean
  isMobile: boolean
  viewMode: 'list' | 'grid'
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setIsMobile: (mobile: boolean) => void
  setViewMode: (mode: 'list' | 'grid') => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: !isMobileDevice(),
  isMobile: isMobileDevice(),
  viewMode: 'list',
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setIsMobile: (mobile) => set({ isMobile: mobile }),
  setViewMode: (mode) => set({ viewMode: mode }),
}))
