import { useState } from 'react'
import { Download, Smartphone, Apple, QrCode, ExternalLink, Check } from 'lucide-react'
import { useInstallPrompt } from '@/hooks/useInstallPrompt'

export default function MobileAppSettings() {
  const { canInstall, isInstalled, install } = useInstallPrompt()
  const [showQR, setShowQR] = useState(false)
  const appUrl = window.location.origin

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Mobile App</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Get O-Brain on your phone for fast access anywhere.</p>
      </div>

      {/* Install status */}
      {isInstalled && (
        <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
          <Check className="w-4 h-4" />
          O-Brain is installed on this device!
        </div>
      )}

      {/* Quick install (if browser supports it) */}
      {canInstall && !isInstalled && (
        <div className="bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl p-6 text-white">
          <div className="flex items-center gap-3 mb-3">
            <Download className="w-6 h-6" />
            <h3 className="font-semibold text-lg">Install O-Brain</h3>
          </div>
          <p className="text-sm text-purple-100 mb-4">
            Install the app for faster access, push notifications, and offline support.
          </p>
          <button
            onClick={install}
            className="px-5 py-2.5 bg-white text-purple-700 font-semibold text-sm rounded-lg hover:bg-purple-50 transition-colors"
          >
            Install Now
          </button>
        </div>
      )}

      {/* Android instructions */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <Smartphone className="w-5 h-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Android</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">Chrome browser</p>
          </div>
        </div>
        <ol className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">1.</span>
            Open <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">{appUrl}</span> in Chrome
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">2.</span>
            Tap the menu icon (three dots) in the top-right corner
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">3.</span>
            Select <strong>"Add to Home Screen"</strong> or <strong>"Install app"</strong>
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">4.</span>
            Tap <strong>"Install"</strong> to confirm
          </li>
        </ol>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 italic">
          Full Android APK coming soon via PWABuilder.
        </p>
      </div>

      {/* iOS instructions */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
            <Apple className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">iPhone & iPad</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">Safari browser</p>
          </div>
        </div>
        <ol className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">1.</span>
            Open <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">{appUrl}</span> in Safari
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">2.</span>
            Tap the <strong>Share</strong> button (square with arrow)
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">3.</span>
            Scroll down and tap <strong>"Add to Home Screen"</strong>
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-gray-900 dark:text-white shrink-0">4.</span>
            Tap <strong>"Add"</strong> in the top-right corner
          </li>
        </ol>
      </div>

      {/* QR Code */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <QrCode className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">QR Code</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">Open on another device</p>
            </div>
          </div>
          <button
            onClick={() => setShowQR(!showQR)}
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            {showQR ? 'Hide' : 'Show QR'}
          </button>
        </div>
        {showQR && (
          <div className="flex flex-col items-center gap-3 py-4">
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(appUrl)}&bgcolor=0f172a&color=a78bfa`}
              alt="QR code to open O-Brain"
              className="w-48 h-48 rounded-lg"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500">Scan with your phone camera to open O-Brain</p>
          </div>
        )}
      </div>

      {/* Web app link */}
      <div className="text-center">
        <a
          href={appUrl}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          {appUrl}
        </a>
      </div>
    </div>
  )
}
