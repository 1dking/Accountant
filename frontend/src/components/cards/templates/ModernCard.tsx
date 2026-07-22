import { Mail, Phone, Globe, CalendarDays, QrCode, UserPlus } from 'lucide-react'
import type { CardTemplateProps } from '../types'

/** Modern — accent banner, left-aligned overlap layout (Arivio modern.tsx). */
export default function ModernCard({ card, onSaveContact, onShowQr }: CardTemplateProps) {
  const initials = card.display_name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div
      className="min-h-screen"
      style={{ background: card.bg_color, color: card.text_color, fontFamily: card.font }}
    >
      <div className="h-36" style={{ background: card.accent_color }} />
      <div className="max-w-sm mx-auto px-6 -mt-14 pb-10">
        {card.avatar_url ? (
          <img
            src={card.avatar_url}
            alt={card.display_name}
            className="w-28 h-28 rounded-2xl object-cover border-4 shadow-lg"
            style={{ borderColor: card.bg_color }}
          />
        ) : (
          <div
            className="w-28 h-28 rounded-2xl flex items-center justify-center text-3xl font-bold text-white border-4 shadow-lg"
            style={{ background: card.button_color, borderColor: card.bg_color }}
          >
            {initials}
          </div>
        )}

        <div className="mt-4 flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">{card.display_name}</h1>
            {(card.job_title || card.company_name) && (
              <p className="mt-0.5 text-sm opacity-70">
                {[card.job_title, card.company_name].filter(Boolean).join(' · ')}
              </p>
            )}
          </div>
          {card.logo_url && <img src={card.logo_url} alt="" className="h-8 object-contain mt-1" />}
        </div>

        {card.tagline && <p className="mt-3 text-sm opacity-80">{card.tagline}</p>}

        <div className="mt-6 grid grid-cols-2 gap-2.5">
          <button
            onClick={onSaveContact}
            className="flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold"
            style={{ background: card.button_color, color: card.button_text_color }}
          >
            <UserPlus className="w-4 h-4" /> Save
          </button>
          {card.booking_url ? (
            <a
              href={card.booking_url}
              className="flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold border"
              style={{ borderColor: card.accent_color, color: card.accent_color }}
            >
              <CalendarDays className="w-4 h-4" /> Book
            </a>
          ) : (
            <button
              onClick={onShowQr}
              className="flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold border"
              style={{ borderColor: card.accent_color, color: card.accent_color }}
            >
              <QrCode className="w-4 h-4" /> Share
            </button>
          )}
        </div>

        <div className="mt-6 divide-y" style={{ borderColor: `${card.text_color}22` }}>
          {card.email && (
            <a href={`mailto:${card.email}`} className="flex items-center gap-3 py-3 text-sm opacity-80 hover:opacity-100">
              <Mail className="w-4 h-4 shrink-0" style={{ color: card.accent_color }} /> {card.email}
            </a>
          )}
          {card.phone && (
            <a href={`tel:${card.phone}`} className="flex items-center gap-3 py-3 text-sm opacity-80 hover:opacity-100">
              <Phone className="w-4 h-4 shrink-0" style={{ color: card.accent_color }} /> {card.phone}
            </a>
          )}
          {card.website && (
            <a href={card.website} target="_blank" rel="noreferrer" className="flex items-center gap-3 py-3 text-sm opacity-80 hover:opacity-100">
              <Globe className="w-4 h-4 shrink-0" style={{ color: card.accent_color }} />
              {card.website.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>

        {Object.keys(card.social_links).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            {Object.entries(card.social_links).map(([label, url]) => (
              <a
                key={label}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1 rounded-full text-xs font-medium capitalize"
                style={{ background: `${card.accent_color}22`, color: card.accent_color }}
              >
                {label}
              </a>
            ))}
          </div>
        )}

        {card.booking_url && (
          <button onClick={onShowQr} className="mt-8 inline-flex items-center gap-1.5 text-xs opacity-50 hover:opacity-90">
            <QrCode className="w-3.5 h-3.5" /> Share this card
          </button>
        )}
      </div>
    </div>
  )
}
