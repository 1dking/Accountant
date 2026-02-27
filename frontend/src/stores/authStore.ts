import { create } from 'zustand'
import { api } from '@/api/client'

interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'accountant' | 'viewer'
  is_active: boolean
  created_at: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: true,

  login: async (email: string, password: string) => {
    const response: any = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', response.data.access_token)
    localStorage.setItem('refresh_token', response.data.refresh_token)
    set({ isAuthenticated: true })
    await get().fetchMe()
  },

  register: async (email: string, password: string, fullName: string) => {
    await api.post('/auth/register', { email, password, full_name: fullName })
  },

  logout: async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      try {
        await api.post('/auth/logout', { refresh_token: refreshToken })
      } catch {
        // Ignore errors during logout
      }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isAuthenticated: false })
  },

  fetchMe: async () => {
    try {
      const response: any = await api.get('/auth/me')
      set({ user: response.data, isAuthenticated: true, isLoading: false })
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false })
    }
  },

  initialize: async () => {
    const token = localStorage.getItem('access_token')
    if (token) {
      await get().fetchMe()
    } else {
      set({ isLoading: false })
    }
  },
}))
