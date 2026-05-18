/**
 * Thin compatibility wrapper around the new Dialer drawer + trigger.
 *
 * Header.tsx still imports this file and mounts <FloatingDialer />,
 * so we keep the export shape but delegate everything to the new
 * components under components/dialer/. State is owned here so the
 * Twilio device + drawer-open flag live in the same scope.
 */
import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import DialerDrawer from '@/components/dialer/DialerDrawer'
import DialerTrigger from '@/components/dialer/DialerTrigger'
import { useTwilioDevice } from '@/components/dialer/hooks/useTwilioDevice'

export default function FloatingDialer() {
  const { isAuthenticated } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)

  const device = useTwilioDevice({
    enabled: isAuthenticated,
    // Incoming call → pop the drawer open so the user sees the
    // accept/reject UI without having to click the header button.
    onIncoming: () => setIsOpen(true),
  })

  if (!isAuthenticated) return null

  return (
    <>
      <DialerTrigger
        mode={device.mode}
        incomingNumber={device.incomingNumber}
        errorMsg={device.errorMsg}
        isOpen={isOpen}
        onClick={() => setIsOpen((o) => !o)}
      />
      <DialerDrawer
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        device={device}
      />
    </>
  )
}
