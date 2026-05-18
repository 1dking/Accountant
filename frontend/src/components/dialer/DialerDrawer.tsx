/**
 * Slide-out dialer drawer.
 *
 * Renders the right-edge Liquid Glass surface, backdrop, drawer
 * header (close + dialer title — gets "Calling From" treatment in
 * commit 2). Body switches on Twilio mode:
 *   - incoming-ringing / in-call / outgoing-connecting / requesting-mic
 *     / permission-denied / error → dedicated call-state panel
 *   - idle / initializing / ready → KeypadView (placeholder body;
 *     commit 2 wraps it in a 5-tab framework)
 *
 * State ownership: the parent (FloatingDialer wrapper) owns the
 * Twilio state (via useTwilioDevice) and the drawer's open flag.
 * This component is presentational + handles keyboard + focus trap.
 */
import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Phone, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TwilioDeviceState } from './hooks/useTwilioDevice'
import CallingPanel from './panels/CallingPanel'
import ErrorPanel from './panels/ErrorPanel'
import InCallPanel from './panels/InCallPanel'
import IncomingPanel from './panels/IncomingPanel'
import KeypadView from './panels/KeypadView'
import PermissionDeniedPanel from './panels/PermissionDeniedPanel'

import './liquid-glass.css'

interface Props {
  isOpen: boolean
  onClose: () => void
  device: TwilioDeviceState
}

export default function DialerDrawer({ isOpen, onClose, device }: Props) {
  const {
    mode, errorMsg, durationSeconds, isMuted, incomingNumber,
    dial, hangup, acceptIncoming, rejectIncoming, toggleMute, retryInit,
  } = device

  // Keypad input is owned here because it's a transient UI buffer —
  // the underlying dial() takes the final string. The number persists
  // across drawer open/close so users can re-open and resume typing.
  const [number, setNumber] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  // Render flag — keep the drawer in the DOM through its exit animation
  // so the slide-out reads naturally. Cleared 200ms after isOpen flips
  // false (matches the .lg-drawer-exit duration).
  const [shouldRender, setShouldRender] = useState(isOpen)
  useEffect(() => {
    if (isOpen) {
      setShouldRender(true)
    } else {
      const t = window.setTimeout(() => setShouldRender(false), 220)
      return () => window.clearTimeout(t)
    }
  }, [isOpen])

  // Escape closes the drawer — always honored as an explicit user
  // action, even mid-call. Suppress backdrop click-out when a call is
  // active (incoming / in-call) so the user can't accidentally dismiss
  // an active call by clicking off-drawer.
  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, onClose])

  // Basic focus trap: when the drawer opens, move focus inside; when
  // it closes, return focus to whatever was previously focused.
  useEffect(() => {
    if (!isOpen) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    // Move focus into the drawer on next tick so the animation has
    // mounted the surface.
    const t = window.setTimeout(() => {
      const focusable = drawerRef.current?.querySelector<HTMLElement>(
        'input, button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
      focusable?.focus()
    }, 0)
    return () => {
      window.clearTimeout(t)
      previouslyFocused?.focus?.()
    }
  }, [isOpen])

  const callIsActive = mode === 'incoming-ringing' || mode === 'in-call'
  const handleBackdropClick = () => {
    if (callIsActive) return
    onClose()
  }

  const handleDial = () => {
    void dial(number)
  }
  const handleDigit = (d: string) => setNumber((prev) => prev + d)
  const handleBackspace = () => setNumber((prev) => prev.slice(0, -1))

  if (!shouldRender) return null

  return (
    <div
      className="fixed inset-0 z-50"
      role="presentation"
      aria-hidden={!isOpen}
    >
      {/* Backdrop */}
      <div
        onClick={handleBackdropClick}
        className={cn(
          'absolute inset-0 bg-black/40',
          isOpen ? 'lg-backdrop-enter' : 'opacity-0 transition-opacity duration-200',
        )}
      />

      {/* Drawer surface */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Dialer"
        className={cn(
          'lg-drawer lg-drawer-surface',
          'absolute right-0 top-0 h-full',
          'w-full md:w-[480px]',
          'flex flex-col',
          isOpen ? 'lg-drawer-enter' : 'lg-drawer-exit',
        )}
      >
        <div className="lg-drawer-content flex flex-col h-full">
          {/* Drawer header — commit 1 ships a minimal version. Commit 2
              upgrades this to "Calling From {twilio_number}" with the
              wave indicator. */}
          <header className="flex items-center justify-between px-5 py-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-[color:var(--lg-text-secondary)]" />
              <span className="text-sm font-semibold tracking-wide text-[color:var(--lg-text-primary)]">
                Dialer
              </span>
            </div>
            <button
              onClick={onClose}
              aria-label="Close dialer"
              className="p-1.5 rounded-md text-[color:var(--lg-text-secondary)] hover:text-[color:var(--lg-text-primary)] hover:bg-white/8 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          {errorMsg && mode !== 'error' && (
            <div className="px-5 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-300 flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 truncate" title={errorMsg}>{errorMsg}</span>
            </div>
          )}

          {/* Body — call states take over, otherwise show the keypad */}
          <div className="flex-1 overflow-y-auto">
            {mode === 'incoming-ringing' && (
              <IncomingPanel
                fromNumber={incomingNumber}
                onAccept={() => { void acceptIncoming() }}
                onReject={rejectIncoming}
              />
            )}

            {mode === 'in-call' && (
              <InCallPanel
                remoteNumber={incomingNumber || number}
                durationSeconds={durationSeconds}
                isMuted={isMuted}
                onMute={toggleMute}
                onHangup={hangup}
              />
            )}

            {(mode === 'outgoing-connecting' || mode === 'requesting-mic') && (
              <CallingPanel target={number} mode={mode} onHangup={hangup} />
            )}

            {mode === 'permission-denied' && <PermissionDeniedPanel />}

            {mode === 'error' && (
              <ErrorPanel message={errorMsg} onRetry={retryInit} />
            )}

            {(mode === 'idle' || mode === 'initializing' || mode === 'ready') && (
              <KeypadView
                number={number}
                setNumber={setNumber}
                onDigit={handleDigit}
                onBackspace={handleBackspace}
                onCall={handleDial}
                inputRef={inputRef}
                disabled={mode !== 'ready'}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
