import { create } from 'zustand'
import { api } from '@/api/client'
import type { Notification } from '@/types/models'

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  isLoading: boolean
  fetchNotifications: () => Promise<void>
  markRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
  deleteNotification: (id: string) => Promise<void>
  addNotification: (notification: Notification) => void
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  unreadCount: 0,
  isLoading: false,

  fetchNotifications: async () => {
    set({ isLoading: true })
    try {
      const response: any = await api.get('/notifications?page_size=50')
      set({
        notifications: response.data,
        unreadCount: response.meta?.unread_count ?? 0,
        isLoading: false,
      })
    } catch {
      set({ isLoading: false })
    }
  },

  markRead: async (id: string) => {
    await api.put(`/notifications/${id}/read`)
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, is_read: true } : n
      ),
      unreadCount: Math.max(0, state.unreadCount - 1),
    }))
  },

  markAllRead: async () => {
    await api.put('/notifications/read-all')
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }))
  },

  deleteNotification: async (id: string) => {
    await api.delete(`/notifications/${id}`)
    set((state) => {
      const removed = state.notifications.find((n) => n.id === id)
      return {
        notifications: state.notifications.filter((n) => n.id !== id),
        unreadCount: removed && !removed.is_read
          ? Math.max(0, state.unreadCount - 1)
          : state.unreadCount,
      }
    })
  },

  addNotification: (notification: Notification) => {
    set((state) => ({
      notifications: [notification, ...state.notifications],
      unreadCount: state.unreadCount + 1,
    }))
  },
}))
