/**
 * Thin compatibility wrapper around the new Dialer drawer + trigger.
 *
 * Header.tsx still imports this file and mounts <FloatingDialer />,
 * so we keep the export shape but delegate everything to the new
 * components under components/dialer/. State is owned here so the
 * Twilio device + drawer-open flag live in the same scope.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { listPhoneNumbers } from '@/api/communication'
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

  // "Calling From" header — first Twilio number returned by the
  // phone-numbers endpoint (backend filters to numbers assigned to
  // the caller). Multi-number selector is a future refinement; most
  // users have one assigned number.
  const phoneNumbersQuery = useQuery({
    queryKey: ['dialer-calling-from'],
    queryFn: () => listPhoneNumbers(),
    enabled: isAuthenticated,
    staleTime: 5 * 60_000,
  })
  const callingFrom = phoneNumbersQuery.data?.data?.[0]?.phone_number ?? null

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
        callingFrom={callingFrom}
      />
    </>
  )
}
