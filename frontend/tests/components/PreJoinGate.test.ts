/**
 * PreJoinGate — Commit 10. Static-parse invariants:
 *
 *  - Component imports LiveKit's <PreJoin> and wires onSubmit into a
 *    gate.
 *  - When record_meeting=true, the gate intercepts onSubmit and shows
 *    a consent overlay (we check for the overlay component name + the
 *    consent-checkbox + the "Join meeting" CTA).
 *  - MeetingRoomPage + MeetingJoinPage both mount PreJoinGate BEFORE
 *    LiveKitRoom (regression guard — easy to forget the gate when
 *    refactoring the connect flow).
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import path from 'path'

const GATE_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'components', 'meetings', 'PreJoinGate.tsx'),
  'utf8',
)
const ROOM_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'pages', 'MeetingRoomPage.tsx'),
  'utf8',
)
const JOIN_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'pages', 'MeetingJoinPage.tsx'),
  'utf8',
)

describe('PreJoinGate (Commit 10)', () => {
  it('imports LiveKit PreJoin and LocalUserChoices', () => {
    expect(GATE_SRC).toMatch(/from\s+['"]@livekit\/components-react['"]/)
    expect(GATE_SRC).toMatch(/PreJoin/)
    expect(GATE_SRC).toMatch(/LocalUserChoices/)
  })

  it('intercepts onSubmit when recordMeeting is true', () => {
    // The gate's onSubmit handler must early-return before calling
    // onJoin when recordMeeting is true and consent hasn't fired.
    expect(GATE_SRC).toMatch(/if\s*\(\s*recordMeeting\s*\)/)
    expect(GATE_SRC).toMatch(/setPendingChoices/)
  })

  it('renders the consent overlay with a required checkbox', () => {
    expect(GATE_SRC).toMatch(/ConsentOverlay/)
    expect(GATE_SRC).toMatch(/I consent/)
    expect(GATE_SRC).toMatch(/type="checkbox"/)
  })

  it('passes pendingChoices to onJoin only after consent', () => {
    // The accept button calls onJoin via handleConsent which reads
    // pendingChoices. The button must be disabled until checked.
    expect(GATE_SRC).toMatch(/handleConsent/)
    expect(GATE_SRC).toMatch(/disabled=\{!checked\}/)
  })
})

describe('PreJoinGate integration (Commit 10)', () => {
  it('MeetingRoomPage mounts PreJoinGate before LiveKitRoom', () => {
    expect(ROOM_SRC).toMatch(/import\s+PreJoinGate/)
    // Gate render must occur before LiveKitRoom render in the JSX flow
    const gateIdx = ROOM_SRC.indexOf('<PreJoinGate')
    const roomIdx = ROOM_SRC.indexOf('<LiveKitRoom')
    expect(gateIdx).toBeGreaterThan(0)
    expect(roomIdx).toBeGreaterThan(gateIdx)
  })

  it('MeetingRoomPage threads userChoices into LiveKitRoom audio/video', () => {
    // Selected devices must flow through to the connect call; otherwise
    // PreJoin's device picker is decorative.
    expect(ROOM_SRC).toMatch(/audioEnabled[\s\S]{0,80}audioDeviceId/)
    expect(ROOM_SRC).toMatch(/videoEnabled[\s\S]{0,80}videoDeviceId/)
  })

  it('MeetingJoinPage gates the admitted state behind PreJoinGate', () => {
    expect(JOIN_SRC).toMatch(/import\s+PreJoinGate/)
    expect(JOIN_SRC).toMatch(/userChoices/)
    // After the lobby admits the guest, the gate renders BEFORE the
    // LiveKitRoom — regression guard against "guest auto-joins without
    // device check". Use the JSX-element-opening forms with newlines
    // / whitespace so we hit the actual render sites, not docstring
    // references to "<LiveKitRoom>".
    const admittedIdx = JOIN_SRC.indexOf("stage === 'admitted'")
    const gateRender = JOIN_SRC.search(/<PreJoinGate\s/)
    const roomRender = JOIN_SRC.search(/<LiveKitRoom\s/)
    expect(gateRender).toBeGreaterThan(admittedIdx)
    expect(roomRender).toBeGreaterThan(gateRender)
  })
})
