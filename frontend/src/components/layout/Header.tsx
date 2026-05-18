import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Menu, Bell, Search, Sparkles, X } from 'lucide-react'
import { useNotificationStore } from '@/stores/notificationStore'
import { useUiStore } from '@/stores/uiStore'
import { formatRelativeTime } from '@/lib/utils'
import FloatingDialer from './FloatingDialer'

export default function Header() {
  const navigate = useNavigate()
  const {
    unreadCount,
    notifications,
    markRead,
    markAllRead,
    fetchNotifications,
    fetchUnreadCount,
    deleteNotification,
  } = useNotificationStore()
  const { panelState, openSidebar, openOBrain, closePanel } = useUiStore()
  const [showNotifications, setShowNotifications] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Initial fetch + 15s polling for unread count while tab is visible.
  // Switches to full fetch when the dropdown opens (load freshest list).
  useEffect(() => {
    let mounted = true
    fetchNotifications().catch(() => {})

    let timer: number | null = null
    const startPolling = () => {
      if (timer !== null) return
      timer = window.setInterval(() => {
        if (mounted && document.visibilityState === 'visible') {
          fetchUnreadCount().catch(() => {})
        }
      }, 15_000)
    }
    const stopPolling = () => {
      if (timer !== null) {
        window.clearInterval(timer)
        timer = null
      }
    }
    const onVisChange = () => {
      if (document.visibilityState === 'visible') {
        // Fire one immediate refresh when the tab regains focus
        fetchUnreadCount().catch(() => {})
        startPolling()
      } else {
        stopPolling()
      }
    }
    startPolling()
    document.addEventListener('visibilitychange', onVisChange)
    return () => {
      mounted = false
      stopPolling()
      document.removeEventListener('visibilitychange', onVisChange)
    }
  }, [fetchNotifications, fetchUnreadCount])

  // When the user opens the dropdown, refresh the full list so they see
  // newest items even if polling was off-window for a while.
  useEffect(() => {
    if (showNotifications) {
      fetchNotifications().catch(() => {})
    }
  }, [showNotifications, fetchNotifications])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/documents?search=${encodeURIComponent(searchQuery.trim())}`)
      setSearchQuery('')
    }
  }

  const handleToggleSidebar = () => {
    if (panelState === 'sidebar') {
      closePanel()
    } else {
      openSidebar()
    }
  }

  const handleToggleOBrain = () => {
    if (panelState === 'obrain') {
      closePanel()
    } else {
      openOBrain()
    }
  }

  return (
    <header className="bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-700 px-4 py-2 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <button
          onClick={handleToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      <form onSubmit={handleSearch} className="flex-1 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50/50 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500"
          />
        </div>
      </form>

      <div className="flex items-center gap-1">
        {/* Phone Dialer — Twilio-wired, state-colored trigger + anchored dropdown */}
        <FloatingDialer />

        {/* O-Brain button */}
        <button
          onClick={handleToggleOBrain}
          className={`relative p-2 rounded-lg transition-colors ${
            panelState === 'obrain'
              ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400'
              : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400'
          }`}
          aria-label="Toggle O-Brain"
          title="O-Brain AI Assistant"
        >
          <Sparkles className="h-5 w-5" />
        </button>

        {/* Notification bell */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 h-4 min-w-4 flex items-center justify-center text-[10px] font-bold text-white bg-red-500 rounded-full px-1">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-full mt-1 w-80 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-50 max-h-96 overflow-hidden">
              <div className="p-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
                <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100">Notifications</h3>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllRead()}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="overflow-y-auto max-h-72">
                {notifications.length === 0 ? (
                  <p className="p-4 text-sm text-gray-500 dark:text-gray-400 text-center">No notifications</p>
                ) : (
                  notifications.slice(0, 20).map((n) => (
                    <div
                      key={n.id}
                      className={`group relative w-full border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/50 transition-colors ${
                        !n.is_read ? 'bg-blue-50/50 dark:bg-blue-900/20' : ''
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          if (!n.is_read) markRead(n.id)
                          // Prefer the explicit link_path set by the
                          // notification creator (new pattern). Fall back to
                          // legacy resource-type routing only when link_path
                          // is empty (older rows / push notifications).
                          if (n.link_path) {
                            navigate(n.link_path)
                          } else if (n.resource_type === 'document' && n.resource_id) {
                            navigate(`/documents/${n.resource_id}`)
                          } else if (n.contact_id) {
                            navigate(`/contacts/${n.contact_id}`)
                          }
                          setShowNotifications(false)
                        }}
                        className="w-full text-left px-4 py-3 pr-9"
                      >
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{n.title}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{n.message}</p>
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          {formatRelativeTime(n.created_at)}
                        </p>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteNotification(n.id)
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Dismiss"
                        aria-label="Dismiss notification"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
