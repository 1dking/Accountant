import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { Menu, Bell, Search, Sparkles, Phone, X, Delete, PhoneCall, PhoneOff } from 'lucide-react'
import { useNotificationStore } from '@/stores/notificationStore'
import { useUiStore } from '@/stores/uiStore'
import { formatRelativeTime, cn } from '@/lib/utils'

const DIALPAD = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

export default function Header() {
  const navigate = useNavigate()
  const { unreadCount, notifications, markRead, markAllRead } = useNotificationStore()
  const { panelState, openSidebar, openOBrain, closePanel } = useUiStore()
  const [showNotifications, setShowNotifications] = useState(false)
  const [showDialer, setShowDialer] = useState(false)
  const [dialNumber, setDialNumber] = useState('')
  const [isCalling, setIsCalling] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const dialerRef = useRef<HTMLDivElement>(null)

  // Close dialer on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dialerRef.current && !dialerRef.current.contains(e.target as Node)) {
        setShowDialer(false)
      }
    }
    if (showDialer) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showDialer])

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
        {/* Phone Dialer */}
        <div className="relative" ref={dialerRef}>
          <button
            onClick={() => { setShowDialer(!showDialer); setShowNotifications(false) }}
            className={`relative p-2 rounded-lg transition-colors ${
              showDialer
                ? 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400'
            }`}
            aria-label="Phone dialer"
            title="Phone Dialer"
          >
            <Phone className="h-5 w-5" />
          </button>

          {showDialer && (
            <div className="absolute right-0 top-full mt-1 w-[280px] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Dialer</span>
                </div>
                <button
                  onClick={() => { setShowDialer(false); setIsCalling(false) }}
                  className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="px-4 pt-3 pb-2">
                <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">
                  <input
                    value={dialNumber}
                    onChange={(e) => setDialNumber(e.target.value.replace(/[^0-9+*#() -]/g, ''))}
                    placeholder="Enter number..."
                    className="flex-1 bg-transparent text-lg font-mono text-gray-900 dark:text-gray-100 placeholder-gray-400 outline-none text-center tracking-wider"
                  />
                  {dialNumber && (
                    <button onClick={() => setDialNumber((p) => p.slice(0, -1))} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                      <Delete className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              <div className="px-4 py-2">
                <div className="grid grid-cols-3 gap-1.5">
                  {DIALPAD.flat().map((digit) => (
                    <button
                      key={digit}
                      onClick={() => setDialNumber((p) => p + digit)}
                      className="h-10 rounded-lg text-lg font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors active:bg-gray-200 dark:active:bg-gray-700"
                    >
                      {digit}
                    </button>
                  ))}
                </div>
              </div>

              <div className="px-4 pb-3 pt-1">
                {isCalling ? (
                  <div className="space-y-2">
                    <div className="text-center text-sm text-gray-500 dark:text-gray-400 animate-pulse">
                      Calling {dialNumber}...
                    </div>
                    <button
                      onClick={() => setIsCalling(false)}
                      className="w-full h-10 rounded-lg bg-red-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-700 transition"
                    >
                      <PhoneOff className="h-4 w-4" />
                      Hang Up
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => { if (dialNumber.trim()) setIsCalling(true) }}
                    disabled={!dialNumber.trim()}
                    className={cn(
                      'w-full h-10 rounded-lg font-medium flex items-center justify-center gap-2 transition',
                      dialNumber.trim()
                        ? 'bg-green-600 text-white hover:bg-green-700'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
                    )}
                  >
                    <PhoneCall className="h-4 w-4" />
                    Call
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

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
                    <button
                      key={n.id}
                      onClick={() => {
                        if (!n.is_read) markRead(n.id)
                        if (n.resource_type === 'document' && n.resource_id) {
                          navigate(`/documents/${n.resource_id}`)
                        }
                        setShowNotifications(false)
                      }}
                      className={`w-full text-left px-4 py-3 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50/50 dark:hover:bg-gray-800/50 transition-colors ${
                        !n.is_read ? 'bg-blue-50/50 dark:bg-blue-900/20' : ''
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{n.title}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{n.message}</p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                        {formatRelativeTime(n.created_at)}
                      </p>
                    </button>
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
