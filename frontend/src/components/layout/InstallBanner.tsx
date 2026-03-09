import { Download, X } from 'lucide-react'
import { useInstallPrompt } from '@/hooks/useInstallPrompt'

export default function InstallBanner() {
  const { showBanner, install, dismiss } = useInstallPrompt()

  if (!showBanner) return null

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm">
      <div className="bg-gray-900 dark:bg-gray-800 text-white rounded-xl shadow-2xl border border-gray-700 p-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-600/20 flex items-center justify-center shrink-0">
            <Download className="w-5 h-5 text-purple-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm">Install O-Brain</p>
            <p className="text-xs text-gray-400 mt-0.5">Get faster access from your home screen</p>
          </div>
          <button onClick={dismiss} className="p-1 text-gray-500 hover:text-gray-300">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <button
            onClick={install}
            className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Install
          </button>
          <button
            onClick={dismiss}
            className="px-4 py-2 text-gray-400 hover:text-white text-sm font-medium transition-colors"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  )
}
