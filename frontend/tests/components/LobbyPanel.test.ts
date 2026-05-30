/**
 * Lobby panel polish for large meetings (Commit 19).
 *
 * Static-parse checks:
 *  - Admit-all button is rendered when 2+ guests waiting
 *  - Scrollable container (max-height + overflow-y: auto) so 10+
 *    waiting guests don't blow up the panel
 *  - admitAllFromLobby API helper exists and iterates the per-row
 *    admit call (the backend's per-row admit stays the source of
 *    truth — no special bulk endpoint)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import path from 'path'

const ROOM_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'pages', 'MeetingRoomPage.tsx'),
  'utf8',
)
const API_SRC = readFileSync(
  path.resolve(__dirname, '..', '..', 'src', 'api', 'meetings.ts'),
  'utf8',
)

describe('LobbyPanel — large-meeting polish (Commit 19)', () => {
  it('renders an Admit-all CTA gated on 2+ waiting guests', () => {
    expect(ROOM_SRC).toMatch(/waiting\.length\s*>=\s*2/)
    expect(ROOM_SRC).toMatch(/admitAllMut/)
    expect(ROOM_SRC).toMatch(/Admit all/)
  })

  it('lobby list container is scrollable for many guests', () => {
    // maxHeight + overflowY:auto ensures 10+ waiting guests don't
    // expand the panel out of viewport
    expect(ROOM_SRC).toMatch(/maxHeight:\s*\d+/)
    expect(ROOM_SRC).toMatch(/overflowY:\s*['"]auto['"]/)
  })

  it('admitAllFromLobby API helper iterates per-row admit', () => {
    // The backend doesn't grow a bulk endpoint — the helper just
    // loops admitFromLobby. Keeps the per-row admit as the source
    // of truth for audit logging.
    expect(API_SRC).toMatch(/admitAllFromLobby/)
    expect(API_SRC).toMatch(/for\s*\(\s*const\s+id\s+of\s+lobbyIds\s*\)/)
  })
})
