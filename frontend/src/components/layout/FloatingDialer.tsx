import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Phone,
  X,
  Delete,
  PhoneCall,
  PhoneOff,
  PhoneIncoming,
  Mic,
  MicOff,
  AlertCircle,
} from 'lucide-react'
import { Device } from '@twilio/voice-sdk'
import { cn } from '@/lib/utils'
import { getCapabilityToken } from '@/api/communication'
import { useAuthStore } from '@/stores/authStore'

const DIALPAD = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['*', '0', '#'],
]

type Mode =
  | 'idle'              // dialer button closed, nothing initialized yet
  | 'initializing'      // dynamic import + token fetch + Device register in flight
  | 'ready'             // Device registered; no active call
  | 'requesting-mic'    // first connect attempt → asking for permission
  | 'permission-denied' // mic denied, show recovery UI
  | 'outgoing-connecting' // dialed out, waiting for accept
  | 'in-call'           // call active (outbound answered OR inbound accepted)
  | 'incoming-ringing'  // incoming call event, awaiting user Accept/Reject
  | 'error'             // init/token/device error — show retry

// Twilio Voice SDK types — using `any` for Call to keep our code resilient
// to minor SDK type evolutions while still benefiting from Device typing.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Call = any

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function FloatingDialer() {
  const { isAuthenticated } = useAuthStore()

  const [isOpen, setIsOpen] = useState(false)
  const [mode, setMode] = useState<Mode>('idle')
  const [number, setNumber] = useState('')
  const [incomingNumber, setIncomingNumber] = useState<string | null>(null)
  const [durationSeconds, setDurationSeconds] = useState(0)
  const [isMuted, setIsMuted] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const deviceRef = useRef<Device | null>(null)
  const callRef = useRef<Call | null>(null)
  const intervalRef = useRef<number | null>(null)
  const initOnceRef = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  // ------------------------------------------------------------------
  // Token helpers
  // ------------------------------------------------------------------
  const fetchToken = useCallback(async (): Promise<string> => {
    const resp = await getCapabilityToken()
    const token = resp.data?.token
    if (!token) throw new Error('No token returned from server')
    return token
  }, [])

  const refreshToken = useCallback(async () => {
    if (!deviceRef.current) return
    try {
      const newToken = await fetchToken()
      deviceRef.current.updateToken(newToken)
      console.info('[Dialer] Twilio token refreshed')
    } catch (err) {
      console.error('[Dialer] Token refresh failed', err)
      setErrorMsg('Voice token refresh failed. Reload page to recover.')
      setMode('error')
    }
  }, [fetchToken])

  // ------------------------------------------------------------------
  // Duration timer
  // ------------------------------------------------------------------
  const startDurationTimer = useCallback(() => {
    setDurationSeconds(0)
    if (intervalRef.current) window.clearInterval(intervalRef.current)
    intervalRef.current = window.setInterval(() => {
      setDurationSeconds((s) => s + 1)
    }, 1000)
  }, [])

  const stopDurationTimer = useCallback(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  // ------------------------------------------------------------------
  // Device lifecycle (lazy dynamic import — keeps SDK out of cold bundle)
  // ------------------------------------------------------------------
  const initDevice = useCallback(async () => {
    if (initOnceRef.current) return
    initOnceRef.current = true
    setMode('initializing')
    setErrorMsg(null)
    try {
      const token = await fetchToken()

      const device = new Device(token, {
        codecPreferences: ['opus' as never, 'pcmu' as never],
        closeProtection: true,
      } as unknown as ConstructorParameters<typeof Device>[1])

      device.on('registered', () => {
        console.info('[Dialer] Device registered for incoming calls')
        setMode('ready')
      })

      device.on('tokenWillExpire', () => {
        console.info('[Dialer] tokenWillExpire — refreshing')
        void refreshToken()
      })

      device.on('error', (err: { code?: number; message?: string }) => {
        console.error('[Dialer] Device error', err)
        setErrorMsg(err.message || 'Voice service error')
      })

      device.on('incoming', (call: Call) => {
        const from = call.parameters?.From || 'Unknown'
        console.info('[Dialer] Incoming call from', from)
        callRef.current = call
        setIncomingNumber(from)
        setMode('incoming-ringing')
        setIsOpen(true) // pop dialer open so user sees the call

        call.on('disconnect', () => {
          console.info('[Dialer] Incoming call disconnected')
          callRef.current = null
          setIncomingNumber(null)
          stopDurationTimer()
          setMode('ready')
        })
        call.on('cancel', () => {
          // Caller hung up before we accepted
          callRef.current = null
          setIncomingNumber(null)
          setMode('ready')
        })
        call.on('accept', () => {
          setMode('in-call')
          startDurationTimer()
        })
        call.on('reject', () => {
          callRef.current = null
          setIncomingNumber(null)
          setMode('ready')
        })
      })

      deviceRef.current = device
      await device.register()
    } catch (err: unknown) {
      console.error('[Dialer] Init failed', err)
      const msg = err instanceof Error ? err.message : 'Voice init failed'
      setErrorMsg(msg)
      setMode('error')
      initOnceRef.current = false // allow retry
    }
  }, [fetchToken, refreshToken, startDurationTimer, stopDurationTimer])

  // Initialize on mount when authenticated. The dynamic import means
  // unauthenticated visitors never load the SDK chunk.
  useEffect(() => {
    if (!isAuthenticated) return
    void initDevice()
    return () => {
      stopDurationTimer()
      if (callRef.current) {
        try {
          callRef.current.disconnect()
        } catch {
          /* ignore */
        }
      }
      if (deviceRef.current) {
        try {
          deviceRef.current.destroy()
        } catch {
          /* ignore */
        }
        deviceRef.current = null
      }
      initOnceRef.current = false
    }
  }, [isAuthenticated, initDevice, stopDurationTimer])

  // ------------------------------------------------------------------
  // User actions
  // ------------------------------------------------------------------
  const handleDigit = (digit: string) => {
    setNumber((prev) => prev + digit)
  }

  const handleBackspace = () => {
    setNumber((prev) => prev.slice(0, -1))
  }

  const handleCall = async () => {
    if (!number.trim() || !deviceRef.current) return
    setErrorMsg(null)

    // Ask for mic permission lazily on first call
    setMode('requesting-mic')
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err) {
      console.error('[Dialer] Mic permission denied', err)
      setMode('permission-denied')
      return
    }

    setMode('outgoing-connecting')
    try {
      const call: Call = await deviceRef.current.connect({
        params: { To: number.trim() },
      })
      callRef.current = call
      call.on('accept', () => {
        setMode('in-call')
        startDurationTimer()
      })
      call.on('disconnect', () => {
        console.info('[Dialer] Outbound call disconnected')
        callRef.current = null
        stopDurationTimer()
        setMode('ready')
      })
      call.on('error', (err: { message?: string }) => {
        console.error('[Dialer] Call error', err)
        setErrorMsg(err.message || 'Call failed')
        setMode('ready')
      })
    } catch (err: unknown) {
      console.error('[Dialer] Connect failed', err)
      const msg = err instanceof Error ? err.message : 'Connect failed'
      setErrorMsg(msg)
      setMode('ready')
    }
  }

  const handleHangup = () => {
    if (callRef.current) {
      try {
        callRef.current.disconnect()
      } catch (err) {
        console.error('[Dialer] Hangup error', err)
      }
    }
    stopDurationTimer()
    setMode('ready')
  }

  const handleAcceptIncoming = async () => {
    if (!callRef.current) return
    // Ensure mic permission before accepting
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setMode('permission-denied')
      return
    }
    callRef.current.accept()
    // The Call's 'accept' event sets mode to 'in-call' + starts timer
  }

  const handleRejectIncoming = () => {
    if (callRef.current) {
      try {
        callRef.current.reject()
      } catch (err) {
        console.error('[Dialer] Reject error', err)
      }
    }
    callRef.current = null
    setIncomingNumber(null)
    setMode('ready')
  }

  const handleToggleMute = () => {
    if (!callRef.current) return
    const next = !isMuted
    callRef.current.mute(next)
    setIsMuted(next)
  }

  const handleRetryInit = () => {
    initOnceRef.current = false
    void initDevice()
  }

  // ------------------------------------------------------------------
  // Click-outside (manual dismissal during incoming/in-call still works
  // via the trigger button; this only blocks AUTO-dismissal)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return
    if (mode === 'incoming-ringing' || mode === 'in-call') return
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, mode])

  // ------------------------------------------------------------------
  // Escape key — always allowed as manual user action, even during call
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen])

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (!isAuthenticated) return null

  const tooltip = tooltipForMode(mode, incomingNumber, errorMsg)

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger — sits inline in the header icon cluster */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        title={tooltip}
        aria-label={tooltip}
        className={cn(
          'relative p-2 rounded-lg transition-colors',
          isOpen
            ? 'bg-gray-100 dark:bg-gray-800'
            : 'hover:bg-gray-50 dark:hover:bg-gray-800'
        )}
      >
        <Phone className={cn('h-5 w-5', iconColorClass(mode))} />
        {mode === 'incoming-ringing' && (
          <span className="absolute inset-0 rounded-lg animate-ping bg-blue-400/20 pointer-events-none" />
        )}
      </button>

      {/* Anchored dropdown — glassmorphic, fade + slide */}
      <div
        className={cn(
          'absolute right-0 top-full mt-1.5 w-[360px] z-50',
          'bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl',
          'border border-gray-200/50 dark:border-gray-700/50',
          'rounded-2xl shadow-2xl overflow-hidden',
          'transition-all duration-150 ease-out',
          isOpen
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 -translate-y-1 pointer-events-none'
        )}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100/70 dark:border-gray-700/70">
          <div className="flex items-center gap-2">
            <Phone className={cn('h-4 w-4', iconColorClass(mode))} />
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Dialer</span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {errorMsg && mode !== 'error' && (
          <div className="px-4 py-2 bg-red-50 dark:bg-red-900/30 text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1 truncate" title={errorMsg}>{errorMsg}</span>
          </div>
        )}

        {/* Body — switches on mode */}
        {mode === 'incoming-ringing' && (
          <IncomingPanel
            fromNumber={incomingNumber}
            onAccept={handleAcceptIncoming}
            onReject={handleRejectIncoming}
          />
        )}

        {mode === 'in-call' && (
          <InCallPanel
            remoteNumber={incomingNumber || number}
            durationSeconds={durationSeconds}
            isMuted={isMuted}
            onMute={handleToggleMute}
            onHangup={handleHangup}
          />
        )}

        {(mode === 'outgoing-connecting' || mode === 'requesting-mic') && (
          <CallingPanel target={number} mode={mode} onHangup={handleHangup} />
        )}

        {mode === 'permission-denied' && <PermissionDeniedPanel />}

        {mode === 'error' && (
          <ErrorPanel message={errorMsg} onRetry={handleRetryInit} />
        )}

        {(mode === 'idle' || mode === 'initializing' || mode === 'ready') && (
          <DialPanel
            number={number}
            setNumber={setNumber}
            onDigit={handleDigit}
            onBackspace={handleBackspace}
            onCall={handleCall}
            inputRef={inputRef}
            disabled={mode !== 'ready'}
          />
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------
// Trigger-icon state helpers
// ------------------------------------------------------------------

function iconColorClass(mode: Mode): string {
  switch (mode) {
    case 'ready':
      return 'text-green-500'
    case 'incoming-ringing':
      return 'text-blue-500'
    case 'in-call':
      return 'text-emerald-500'
    case 'permission-denied':
    case 'error':
      return 'text-red-500'
    default:
      return 'text-gray-400 dark:text-gray-500'
  }
}

function tooltipForMode(
  mode: Mode,
  incomingNumber: string | null,
  errorMsg: string | null
): string {
  switch (mode) {
    case 'idle':
    case 'initializing':
      return 'Phone (initializing…)'
    case 'ready':
      return 'Phone (ready)'
    case 'incoming-ringing':
      return incomingNumber ? `Incoming call from ${incomingNumber}` : 'Incoming call'
    case 'outgoing-connecting':
    case 'requesting-mic':
      return 'Calling…'
    case 'in-call':
      return 'Call in progress'
    case 'permission-denied':
      return 'Microphone access needed'
    case 'error':
      return errorMsg || 'Phone error'
  }
}

// ------------------------------------------------------------------
// Sub-panels
// ------------------------------------------------------------------

function DialPanel({
  number,
  setNumber,
  onDigit,
  onBackspace,
  onCall,
  inputRef,
  disabled,
}: {
  number: string
  setNumber: (n: string) => void
  onDigit: (d: string) => void
  onBackspace: () => void
  onCall: () => void
  inputRef: React.RefObject<HTMLInputElement | null>
  disabled: boolean
}) {
  return (
    <>
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2.5">
          <input
            ref={inputRef}
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/[^0-9+*#() -]/g, ''))}
            placeholder="Enter number..."
            className="flex-1 bg-transparent text-lg font-mono text-gray-900 dark:text-gray-100 placeholder-gray-400 outline-none text-center tracking-wider"
            disabled={disabled}
          />
          {number && (
            <button onClick={onBackspace} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
              <Delete className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      <div className="px-4 py-2">
        <div className="grid grid-cols-3 gap-2">
          {DIALPAD.flat().map((digit) => (
            <button
              key={digit}
              onClick={() => onDigit(digit)}
              disabled={disabled}
              className="h-12 rounded-xl text-lg font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors active:bg-gray-200 dark:active:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {digit}
            </button>
          ))}
        </div>
      </div>
      <div className="px-4 pb-4 pt-2">
        <button
          onClick={onCall}
          disabled={disabled || !number.trim()}
          className={cn(
            'w-full h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition',
            !disabled && number.trim()
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
          )}
        >
          <PhoneCall className="h-5 w-5" />
          {disabled ? 'Connecting…' : 'Call'}
        </button>
      </div>
    </>
  )
}

function CallingPanel({
  target,
  mode,
  onHangup,
}: {
  target: string
  mode: Mode
  onHangup: () => void
}) {
  return (
    <div className="px-4 py-6 space-y-4">
      <div className="text-center">
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
          {mode === 'requesting-mic' ? 'Requesting microphone…' : 'Calling'}
        </div>
        <div className="font-mono text-lg text-gray-900 dark:text-gray-100">{target}</div>
        <div className="text-sm text-gray-400 mt-2 animate-pulse">
          {mode === 'requesting-mic' ? 'Allow microphone access if prompted' : 'Ringing…'}
        </div>
      </div>
      <button
        onClick={onHangup}
        className="w-full h-12 rounded-xl bg-red-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-700"
      >
        <PhoneOff className="h-5 w-5" />
        Cancel
      </button>
    </div>
  )
}

function InCallPanel({
  remoteNumber,
  durationSeconds,
  isMuted,
  onMute,
  onHangup,
}: {
  remoteNumber: string
  durationSeconds: number
  isMuted: boolean
  onMute: () => void
  onHangup: () => void
}) {
  return (
    <div className="px-4 py-6 space-y-4">
      <div className="text-center">
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">In call</div>
        <div className="font-mono text-lg text-gray-900 dark:text-gray-100">{remoteNumber}</div>
        <div className="text-sm text-emerald-600 dark:text-emerald-400 mt-2 font-mono">
          {formatDuration(durationSeconds)}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={onMute}
          className={cn(
            'h-12 rounded-xl font-medium flex items-center justify-center gap-2 transition',
            isMuted
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
          )}
        >
          {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          {isMuted ? 'Unmute' : 'Mute'}
        </button>
        <button
          onClick={onHangup}
          className="h-12 rounded-xl bg-red-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-700"
        >
          <PhoneOff className="h-5 w-5" />
          Hang Up
        </button>
      </div>
    </div>
  )
}

function IncomingPanel({
  fromNumber,
  onAccept,
  onReject,
}: {
  fromNumber: string | null
  onAccept: () => void
  onReject: () => void
}) {
  return (
    <div className="px-4 py-6 space-y-4">
      <div className="text-center">
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 flex items-center justify-center gap-1">
          <PhoneIncoming className="h-3.5 w-3.5 animate-pulse" />
          Incoming call
        </div>
        <div className="font-mono text-lg text-gray-900 dark:text-gray-100">
          {fromNumber || 'Unknown'}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={onReject}
          className="h-12 rounded-xl bg-red-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-red-700"
        >
          <PhoneOff className="h-5 w-5" />
          Reject
        </button>
        <button
          onClick={onAccept}
          className="h-12 rounded-xl bg-emerald-600 text-white font-medium flex items-center justify-center gap-2 hover:bg-emerald-700"
        >
          <PhoneCall className="h-5 w-5" />
          Accept
        </button>
      </div>
    </div>
  )
}

function PermissionDeniedPanel() {
  return (
    <div className="px-4 py-6 space-y-3 text-center">
      <AlertCircle className="h-8 w-8 mx-auto text-red-600 dark:text-red-400" />
      <div>
        <div className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
          Microphone access denied
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Re-enable microphone permission in your browser settings (click the
          lock icon in the address bar) and reload this page.
        </div>
      </div>
    </div>
  )
}

function ErrorPanel({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="px-4 py-6 space-y-3 text-center">
      <AlertCircle className="h-8 w-8 mx-auto text-red-600 dark:text-red-400" />
      <div>
        <div className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
          Dialer unavailable
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 break-words" title={message || undefined}>
          {message || 'Failed to initialize voice'}
        </div>
      </div>
      <button
        onClick={onRetry}
        className="w-full h-10 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
      >
        Retry
      </button>
    </div>
  )
}
