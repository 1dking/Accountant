/**
 * PreJoinGate (Commit 21 — simplified). The previous version wrapped
 * LiveKit's <PreJoin> component for camera preview + device pickers.
 * That created a tangled getUserMedia lifecycle and tracks consistently
 * came up muted in the room. We ripped <PreJoin> out and replaced it
 * with a name field + Join button. Media is acquired exclusively inside
 * <LiveKitRoom> via audio={true}/video={true}, and ForceEnableMediaOnConnect
 * re-enables tracks as a belt-and-suspenders measure.
 *
 * Invariants checked here:
 *  - Gate does NOT import LiveKit's <PreJoin> any more.
 *  - Gate still renders the consent overlay for record_meeting=true.
 *  - Gate emits a LocalUserChoices with audioEnabled+videoEnabled both
 *    true (no muted-on-join).
 *  - MeetingRoomPage + MeetingJoinPage still gate the room behind it,
 *    and ForceEnableMediaOnConnect is wired inside the room.
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

describe('PreJoinGate (Commit 21 — no LK PreJoin)', () => {
  it('does NOT import LiveKit <PreJoin>', () => {
    // The whole reason this commit exists. <PreJoin>'s getUserMedia
    // preview was tangling with the room's getUserMedia → tracks
    // published muted. Never import it back from @livekit/components-react.
    const lkImports = GATE_SRC.match(
      /import\s*\{([^}]*)\}\s*from\s*['"]@livekit\/components-react['"]/,
    )
    expect(lkImports).not.toBeNull()
    const names = (lkImports?.[1] || '').split(',').map((s) => s.trim())
    expect(names).not.toContain('PreJoin')
  })

  it('still imports LocalUserChoices type', () => {
    expect(GATE_SRC).toMatch(/LocalUserChoices/)
  })

  it('joins with mic + cam always enabled', () => {
    // audioEnabled and videoEnabled must be set to true in the choices
    // payload that gets handed up to onJoin. We never carry a "start
    // muted" flag through this gate any more.
    expect(GATE_SRC).toMatch(/audioEnabled:\s*true/)
    expect(GATE_SRC).toMatch(/videoEnabled:\s*true/)
  })

  it('renders the consent overlay with a required checkbox for record_meeting', () => {
    expect(GATE_SRC).toMatch(/ConsentOverlay/)
    expect(GATE_SRC).toMatch(/I consent/)
    expect(GATE_SRC).toMatch(/type="checkbox"/)
    expect(GATE_SRC).toMatch(/disabled=\{!checked\}/)
  })
})

describe('PreJoinGate integration (Commit 21)', () => {
  it('MeetingRoomPage mounts PreJoinGate before LiveKitRoom', () => {
    expect(ROOM_SRC).toMatch(/import\s+PreJoinGate/)
    const gateIdx = ROOM_SRC.indexOf('<PreJoinGate')
    const roomIdx = ROOM_SRC.indexOf('<LiveKitRoom')
    expect(gateIdx).toBeGreaterThan(0)
    expect(roomIdx).toBeGreaterThan(gateIdx)
  })

  it('MeetingRoomPage hardcodes audio + video to true on LiveKitRoom', () => {
    // No more device-id threading. The room acquires default devices.
    expect(ROOM_SRC).toMatch(/audio=\{true\}/)
    expect(ROOM_SRC).toMatch(/video=\{true\}/)
  })

  it('MeetingRoomPage wires ForceEnableMediaOnConnect inside the room', () => {
    // Belt-and-suspenders: this component re-enables mic + cam after
    // connect even if something else left them disabled.
    expect(ROOM_SRC).toMatch(/ForceEnableMediaOnConnect/)
  })

  it('MeetingJoinPage gates the admitted state behind PreJoinGate', () => {
    expect(JOIN_SRC).toMatch(/import\s+PreJoinGate/)
    expect(JOIN_SRC).toMatch(/userChoices/)
    const admittedIdx = JOIN_SRC.indexOf("stage === 'admitted'")
    const gateRender = JOIN_SRC.search(/<PreJoinGate\s/)
    const roomRender = JOIN_SRC.search(/<LiveKitRoom\s/)
    expect(gateRender).toBeGreaterThan(admittedIdx)
    expect(roomRender).toBeGreaterThan(gateRender)
  })

  it('MeetingJoinPage wires GuestForceEnableMediaOnConnect inside the room', () => {
    expect(JOIN_SRC).toMatch(/GuestForceEnableMediaOnConnect/)
  })
})
