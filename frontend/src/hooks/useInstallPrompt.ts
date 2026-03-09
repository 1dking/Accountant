import { useState, useEffect, useCallback } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISS_KEY = 'pwa-install-dismissed'
const DISMISS_DAYS = 7

export function useInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isInstalled, setIsInstalled] = useState(false)
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    // Check if already installed (standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true)
      return
    }

    // Check if dismissed recently
    const dismissed = localStorage.getItem(DISMISS_KEY)
    if (dismissed) {
      const dismissDate = new Date(dismissed)
      const daysSince = (Date.now() - dismissDate.getTime()) / (1000 * 60 * 60 * 24)
      if (daysSince < DISMISS_DAYS) return
    }

    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setShowBanner(true)
    }

    window.addEventListener('beforeinstallprompt', handler)

    // Detect when app is installed
    window.addEventListener('appinstalled', () => {
      setIsInstalled(true)
      setShowBanner(false)
      setDeferredPrompt(null)
    })

    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  const install = useCallback(async () => {
    if (!deferredPrompt) return false
    await deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    setDeferredPrompt(null)
    setShowBanner(false)
    return outcome === 'accepted'
  }, [deferredPrompt])

  const dismiss = useCallback(() => {
    setShowBanner(false)
    localStorage.setItem(DISMISS_KEY, new Date().toISOString())
  }, [])

  return { canInstall: !!deferredPrompt, isInstalled, showBanner, install, dismiss }
}
