import type { PublicCard } from '@/api/cards'

/**
 * Shared contract for the three card templates (Arivio port —
 * templates/types.ts). Palette arrives fully resolved from the server;
 * templates apply it via inline styles, deliberately not CSS vars, so
 * a card renders identically inside the editor preview and the public
 * page regardless of the surrounding app theme.
 */
export interface CardTemplateProps {
  card: PublicCard
  /** Absolute URL of this card, for the QR overlay + share actions. */
  cardUrl: string
  onSaveContact: () => void
  onShowQr: () => void
}
