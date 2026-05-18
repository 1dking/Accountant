/**
 * Twilio Voice Device lifecycle, extracted from the legacy
 * FloatingDialer mega-component.
 *
 * Owns the state machine (mode + duration + mute + errors),
 * the Device + Call refs, token refresh, and the dial/accept/reject/
 * hangup/mute action handlers. Callers receive a flat object that the
 * drawer + panels destructure — no Twilio types leak past this seam.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Device } from '@twilio/voice-sdk'
import { getCapabilityToken } from '@/api/communication'

export type DialerMode =
  | 'idle'
  | 'initializing'
  | 'ready'
  | 'requesting-mic'
  | 'permission-denied'
  | 'outgoing-connecting'
  | 'in-call'
  | 'incoming-ringing'
  | 'error'

// Twilio Voice SDK types are looser than we want — keep our surface
// honest by treating the live Call as `any` only inside this module.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Call = any

export interface TwilioDeviceState {
  mode: DialerMode
  errorMsg: string | null
  durationSeconds: number
  isMuted: boolean
  incomingNumber: string | null

  // Actions
  dial: (number: string) => Promise<void>
  hangup: () => void
  acceptIncoming: () => Promise<void>
  rejectIncoming: () => void
  toggleMute: () => void
  retryInit: () => void

  // Side-effect signal: ‘incoming’ event flips this momentarily so the
  // drawer can pop open. Caller subscribes via the optional onIncoming
  // callback rather than diffing this state.
}

export interface UseTwilioDeviceOptions {
  enabled: boolean
  onIncoming?: () => void
}

export function useTwilioDevice({
  enabled,
  onIncoming,
}: UseTwilioDeviceOptions): TwilioDeviceState {
  const [mode, setMode] = useState<DialerMode>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [durationSeconds, setDurationSeconds] = useState(0)
  const [isMuted, setIsMuted] = useState(false)
  const [incomingNumber, setIncomingNumber] = useState<string | null>(null)

  const deviceRef = useRef<Device | null>(null)
  const callRef = useRef<Call | null>(null)
  const intervalRef = useRef<number | null>(null)
  const initOnceRef = useRef(false)
  const onIncomingRef = useRef(onIncoming)

  // Keep the latest onIncoming callback in a ref so the Device event
  // handler doesn't capture a stale reference.
  useEffect(() => {
    onIncomingRef.current = onIncoming
  }, [onIncoming])

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
        onIncomingRef.current?.()

        call.on('disconnect', () => {
          callRef.current = null
          setIncomingNumber(null)
          stopDurationTimer()
          setMode('ready')
        })
        call.on('cancel', () => {
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
      initOnceRef.current = false
    }
  }, [fetchToken, refreshToken, startDurationTimer, stopDurationTimer])

  useEffect(() => {
    if (!enabled) return
    void initDevice()
    return () => {
      stopDurationTimer()
      if (callRef.current) {
        try { callRef.current.disconnect() } catch { /* ignore */ }
      }
      if (deviceRef.current) {
        try { deviceRef.current.destroy() } catch { /* ignore */ }
        deviceRef.current = null
      }
      initOnceRef.current = false
    }
  }, [enabled, initDevice, stopDurationTimer])

  const dial = useCallback(async (number: string) => {
    const target = number.trim()
    if (!target || !deviceRef.current) return
    setErrorMsg(null)

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
        params: { To: target },
      })
      callRef.current = call
      call.on('accept', () => {
        setMode('in-call')
        startDurationTimer()
      })
      call.on('disconnect', () => {
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
  }, [startDurationTimer, stopDurationTimer])

  const hangup = useCallback(() => {
    if (callRef.current) {
      try { callRef.current.disconnect() } catch (err) {
        console.error('[Dialer] Hangup error', err)
      }
    }
    stopDurationTimer()
    setMode('ready')
  }, [stopDurationTimer])

  const acceptIncoming = useCallback(async () => {
    if (!callRef.current) return
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setMode('permission-denied')
      return
    }
    callRef.current.accept()
  }, [])

  const rejectIncoming = useCallback(() => {
    if (callRef.current) {
      try { callRef.current.reject() } catch (err) {
        console.error('[Dialer] Reject error', err)
      }
    }
    callRef.current = null
    setIncomingNumber(null)
    setMode('ready')
  }, [])

  const toggleMute = useCallback(() => {
    if (!callRef.current) return
    const next = !isMuted
    callRef.current.mute(next)
    setIsMuted(next)
  }, [isMuted])

  const retryInit = useCallback(() => {
    initOnceRef.current = false
    void initDevice()
  }, [initDevice])

  return {
    mode,
    errorMsg,
    durationSeconds,
    isMuted,
    incomingNumber,
    dial,
    hangup,
    acceptIncoming,
    rejectIncoming,
    toggleMute,
    retryInit,
  }
}
