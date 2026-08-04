import { create } from 'zustand'
import { api } from '@/api/client'
import { passkeyLogin } from '@/api/webauthn'

export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'manager' | 'team_member' | 'accountant' | 'client' | 'viewer'
  is_active: boolean
  created_at: string
  feature_access: Record<string, boolean> | null
  org_id: string | null
  manager_id: string | null
  cashbook_access: 'personal' | 'org'
  active_mode?: 'business' | 'personal'
  fallback_phone: string | null
  voicemail_mode?: 'cell_then_voicemail' | 'voicemail_only' | 'cell_only'
  voicemail_greeting_status?: 'audio' | 'text' | null
  booking_link?: string | null
  conversation_reply_enabled?: boolean
  conversation_template?: string | null
  conversation_ai_instructions?: string | null
  identity_capture_enabled?: boolean
}

/** Result of a password login: either fully signed in, or a second factor is
 *  required (the caller then completes it with a passkey or a TOTP code). */
export interface LoginResult {
  mfaRequired: boolean
  mfaToken?: string
  methods?: string[]
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<LoginResult>
  completePasskeyLogin: (mfaToken: string) => Promise<void>
  completeTotpLogin: (mfaToken: string, code: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => {
  const finalize = async (accessToken: string, refreshToken: string) => {
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    set({ isAuthenticated: true })
    await get().fetchMe()
  }

  return {
    user: null,
    isAuthenticated: !!localStorage.getItem('access_token'),
    isLoading: true,

    login: async (email: string, password: string): Promise<LoginResult> => {
      const response: any = await api.post('/auth/login', { email, password })
      const data = response.data || {}
      // MFA users (TOTP or passkey) get a challenge, NOT tokens. Do not try to
      // store an undefined token — hand the challenge back to the login page.
      if (data.mfa_required) {
        return { mfaRequired: true, mfaToken: data.mfa_token, methods: data.methods || [] }
      }
      await finalize(data.access_token, data.refresh_token)
      return { mfaRequired: false }
    },

    completePasskeyLogin: async (mfaToken: string) => {
      const resp: any = await passkeyLogin(mfaToken)
      await finalize(resp.data.access_token, resp.data.refresh_token)
    },

    completeTotpLogin: async (mfaToken: string, code: string) => {
      const resp: any = await api.post('/auth/mfa/login', { mfa_token: mfaToken, code })
      await finalize(resp.data.access_token, resp.data.refresh_token)
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
        // On a fresh device (no local choice yet) adopt the server's remembered
        // ledger so Personal/Business persists across devices. Imported lazily to
        // avoid a store import cycle.
        const mode = response.data?.active_mode
        if ((mode === 'business' || mode === 'personal') && !localStorage.getItem('app_mode')) {
          const { useUiStore } = await import('@/stores/uiStore')
          useUiStore.getState().setMode(mode)
        }
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
  }
})
