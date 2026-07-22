import { QrCode } from 'lucide-react'
import type { CardTemplateProps } from '../types'

/** Minimal — typographic, no avatar, understated links (Arivio minimal.tsx). */
export default function MinimalCard({ card, onSaveContact, onShowQr }: CardTemplateProps) {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-6 py-10"
      style={{ background: card.bg_color, color: card.text_color, fontFamily: card.font }}
    >
      <div className="w-full max-w-sm">
        {card.logo_url && <img src={card.logo_url} alt="" className="h-7 mb-10 object-contain" />}

        <h1 className="text-3xl font-bold tracking-tight">{card.display_name}</h1>
        {(card.job_title || card.company_name) && (
          <p className="mt-2 text-sm opacity-60">
            {[card.job_title, card.company_name].filter(Boolean).join(' — ')}
          </p>
        )}
        {card.tagline && <p className="mt-5 text-sm leading-relaxed opacity-80">{card.tagline}</p>}

        <div className="mt-8 space-y-2 text-sm">
          {card.email && (
            <p>
              <a href={`mailto:${card.email}`} className="underline decoration-2 underline-offset-4" style={{ textDecorationColor: card.accent_color }}>
                {card.email}
              </a>
            </p>
          )}
          {card.phone && (
            <p>
              <a href={`tel:${card.phone}`} className="underline decoration-2 underline-offset-4" style={{ textDecorationColor: card.accent_color }}>
                {card.phone}
              </a>
            </p>
          )}
          {card.website && (
            <p>
              <a href={card.website} target="_blank" rel="noreferrer" className="underline decoration-2 underline-offset-4" style={{ textDecorationColor: card.accent_color }}>
                {card.website.replace(/^https?:\/\//, '')}
              </a>
            </p>
          )}
          {Object.entries(card.social_links).map(([label, url]) => (
            <p key={label}>
              <a href={url} target="_blank" rel="noreferrer" className="underline decoration-2 underline-offset-4 capitalize" style={{ textDecorationColor: card.accent_color }}>
                {label}
              </a>
            </p>
          ))}
        </div>

        <div className="mt-10 flex items-center gap-3">
          <button
            onClick={onSaveContact}
            className="rounded-md px-4 py-2 text-sm font-semibold"
            style={{ background: card.button_color, color: card.button_text_color }}
          >
            Save Contact
          </button>
          {card.booking_url && (
            <a href={card.booking_url} className="text-sm font-medium" style={{ color: card.accent_color }}>
              Book a meeting →
            </a>
          )}
        </div>

        <button onClick={onShowQr} className="mt-10 inline-flex items-center gap-1.5 text-xs opacity-40 hover:opacity-80">
          <QrCode className="w-3.5 h-3.5" /> Share
        </button>
      </div>
    </div>
  )
}
