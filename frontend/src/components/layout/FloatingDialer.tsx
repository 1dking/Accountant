import { useState, useRef } from 'react'
import { Phone, X, Delete, PhoneCall, PhoneOff } from 'lucide-react'
import { cn } from '@/lib/utils'

const DIALPAD = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

export default function FloatingDialer() {
  const [isOpen, setIsOpen] = useState(false)
  const [number, setNumber] = useState('')
  const [calling, setCalling] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDigit = (digit: string) => {
    setNumber((prev) => prev + digit)
  }

  const handleBackspace = () => {
    setNumber((prev) => prev.slice(0, -1))
  }

  const handleCall = () => {
    if (!number.trim()) return
    setCalling(true)
    // Placeholder — actual Twilio integration connects here
    setTimeout(() => setCalling(false), 3000)
  }

  const handleHangup = () => {
    setCalling(false)
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-green-600 text-white shadow-lg hover:bg-green-700 flex items-center justify-center transition-all hover:scale-105"
        title="Open dialer"
      >
        <Phone className="h-6 w-6" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[300px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-green-600" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Dialer</span>
        </div>
        <button
          onClick={() => { setIsOpen(false); setCalling(false) }}
          className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Number display */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2.5">
          <input
            ref={inputRef}
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/[^0-9+*#() -]/g, ''))}
            placeholder="Enter number..."
            className="flex-1 bg-transparent text-lg font-mono text-gray-900 dark:text-gray-100 placeholder-gray-400 outline-none text-center tracking-wider"
          />
          {number && (
            <button onClick={handleBackspace} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
              <Delete className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Dialpad */}
      <div className="px-4 py-2">
        <div className="grid grid-cols-3 gap-2">
          {DIALPAD.flat().map((digit) => (
            <button
              key={digit}
              onClick={() => handleDigit(digit)}
              className="h-12 rounded-xl text-lg font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors active:bg-gray-200 dark:active:bg-gray-700"
            >
              {digit}
            </button>
          ))}
        </div>
      </div>

      {/* Call button */}
      <div className="px-4 pb-4 pt-2">
        {calling ? (
          <div className="space-y-2">
            <div className="text-center text-sm text-gray-500 dark:text-gray-400 animate-pulse">
              Calling {number}...
            </div>
            <button
              onClick={handleHangup}
              className="w-full h-12 rounded-xl bg-red-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-700 transition"
            >
              <PhoneOff className="h-5 w-5" />
              Hang Up
            </button>
          </div>
        ) : (
          <button
            onClick={handleCall}
            disabled={!number.trim()}
            className={cn(
              'w-full h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition',
              number.trim()
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
            )}
          >
            <PhoneCall className="h-5 w-5" />
            Call
          </button>
        )}
      </div>
    </div>
  )
}
