/**
 * Slide-out dialer drawer with 5-tab content framework.
 *
 * Body switches on Twilio mode FIRST — active call states take over
 * the whole drawer (incoming, in-call, calling, mic-denied, error).
 * Otherwise the body renders the persistent "Calling From" header,
 * a 5-tab nav, and the active tab's content.
 *
 * Dialing a number from any tab routes through the same Twilio
 * device.dial() — Recents/Contacts/Keypad all funnel into one call
 * pipeline. The keypad input string is owned here so it persists
 * across drawer open/close and across tab switches.
 */
import { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TwilioDeviceState } from './hooks/useTwilioDevice'
import CallingPanel from './panels/CallingPanel'
import ErrorPanel from './panels/ErrorPanel'
import InCallPanel from './panels/InCallPanel'
import IncomingPanel from './panels/IncomingPanel'
import PermissionDeniedPanel from './panels/PermissionDeniedPanel'
import DialerCommandPalette from './DialerCommandPalette'
import DialerHeader from './DialerHeader'
import DialerTabBar, { type DialerTabKey } from './DialerTabBar'
import ContactsTab from './tabs/ContactsTab'
import KeypadTab from './tabs/KeypadTab'
import QueueTab from './tabs/QueueTab'
import RecentsTab from './tabs/RecentsTab'
import VoicemailTab from './tabs/VoicemailTab'

import './liquid-glass.css'

interface Props {
  isOpen: boolean
  onClose: () => void
  device: TwilioDeviceState
  callingFrom: string | null
}

export default function DialerDrawer({ isOpen, onClose, device, callingFrom }: Props) {
  const {
    mode, errorMsg, durationSeconds, isMuted, incomingNumber,
    dial, hangup, acceptIncoming, rejectIncoming, toggleMute, retryInit,
  } = device

  // Persistent state across drawer open/close.
  const [number, setNumber] = useState('')
  const [activeTab, setActiveTab] = useState<DialerTabKey>('recents')

  const drawerRef = useRef<HTMLDivElement>(null)

  // Keep the drawer mounted through its exit animation so the slide
  // out reads naturally. Cleared 200ms after isOpen flips false.
  const [shouldRender, setShouldRender] = useState(isOpen)
  useEffect(() => {
    if (isOpen) {
      setShouldRender(true)
    } else {
      const t = window.setTimeout(() => setShouldRender(false), 220)
      return () => window.clearTimeout(t)
    }
  }, [isOpen])

  // Escape closes the drawer — explicit user action wins even during
  // active calls. Click-out is suppressed during calls so users can't
  // accidentally dismiss an active call by clicking off-drawer.
  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, onClose])

  // Basic focus trap: focus the first focusable on open, return focus
  // to whatever was previously focused on close.
  useEffect(() => {
    if (!isOpen) return
    const prev = document.activeElement as HTMLElement | null
    const t = window.setTimeout(() => {
      const focusable = drawerRef.current?.querySelector<HTMLElement>(
        'input, button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
      focusable?.focus()
    }, 0)
    return () => {
      window.clearTimeout(t)
      prev?.focus?.()
    }
  }, [isOpen])

  const callIsActive = mode === 'incoming-ringing' || mode === 'in-call'
  const handleBackdropClick = () => {
    if (callIsActive) return
    onClose()
  }

  // Unified dial helper: any tab that initiates a call routes the
  // number into local keypad state (so the Calling/InCall panels can
  // display it) and fires device.dial.
  const handleDial = (raw: string) => {
    const trimmed = raw.trim()
    if (!trimmed) return
    setNumber(trimmed)
    void dial(trimmed)
  }

  if (!shouldRender) return null

  // Active-call states get a full-drawer takeover; the tabbed body
  // hides until the call clears. The "Calling From" header stays at
  // the top either way so the user always knows the source number.
  const renderBody = () => {
    if (mode === 'incoming-ringing') {
      return (
        <IncomingPanel
          fromNumber={incomingNumber}
          onAccept={() => { void acceptIncoming() }}
          onReject={rejectIncoming}
        />
      )
    }
    if (mode === 'in-call') {
      return (
        <InCallPanel
          remoteNumber={incomingNumber || number}
          durationSeconds={durationSeconds}
          isMuted={isMuted}
          onMute={toggleMute}
          onHangup={hangup}
        />
      )
    }
    if (mode === 'outgoing-connecting' || mode === 'requesting-mic') {
      return <CallingPanel target={number} mode={mode} onHangup={hangup} />
    }
    if (mode === 'permission-denied') return <PermissionDeniedPanel />
    if (mode === 'error') return <ErrorPanel message={errorMsg} onRetry={retryInit} />

    // Idle / initializing / ready → command palette + tabbed content
    return (
      <div className="flex flex-col h-full">
        <DialerCommandPalette onDial={handleDial} />
        <DialerTabBar active={activeTab} onChange={setActiveTab} />
        <div className="flex-1 overflow-y-auto min-h-0">
          {activeTab === 'recents' && <RecentsTab onDial={handleDial} />}
          {activeTab === 'contacts' && <ContactsTab onDial={handleDial} />}
          {activeTab === 'keypad' && (
            <KeypadTab
              number={number}
              setNumber={setNumber}
              onDigit={(d) => setNumber((prev) => prev + d)}
              onBackspace={() => setNumber((prev) => prev.slice(0, -1))}
              onCall={() => handleDial(number)}
              disabled={mode !== 'ready'}
            />
          )}
          {activeTab === 'voicemail' && <VoicemailTab />}
          {activeTab === 'queue' && <QueueTab />}
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50" role="presentation" aria-hidden={!isOpen}>
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
          <DialerHeader callingFrom={callingFrom} mode={mode} onClose={onClose} />

          {errorMsg && mode !== 'error' && (
            <div className="px-5 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-300 flex items-center gap-2 shrink-0">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 truncate" title={errorMsg}>{errorMsg}</span>
            </div>
          )}

          <div className="flex-1 min-h-0">{renderBody()}</div>
        </div>
      </div>
    </div>
  )
}
