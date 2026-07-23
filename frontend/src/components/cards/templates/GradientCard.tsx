import { Mail, Phone, Globe, CalendarDays, QrCode, UserPlus } from 'lucide-react'
import type { CardTemplateProps } from '../types'

/** Gradient — full accent→button gradient backdrop with a floating glass panel. */
export default function GradientCard({ card, onSaveContact, onShowQr }: CardTemplateProps) {
  const initials = card.display_name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div
      className="min-h-screen flex items-center justify-center px-5 py-10"
      style={{
        background: `linear-gradient(160deg, ${card.accent_color} 0%, ${card.button_color} 100%)`,
        fontFamily: card.font,
      }}
    >
      <div
        className="w-full max-w-sm rounded-3xl shadow-2xl px-6 py-8 text-center backdrop-blur"
        style={{ background: card.bg_color, color: card.text_color }}
      >
        {card.logo_url && (
          <img src={card.logo_url} alt="" className="h-7 mx-auto mb-5 object-contain" />
        )}

        {card.avatar_url ? (
          <img
            src={card.avatar_url}
            alt={card.display_name}
            className="w-24 h-24 rounded-full object-cover mx-auto -mt-20 border-4 shadow-lg"
            style={{ borderColor: card.bg_color }}
          />
        ) : (
          <div
            className="w-24 h-24 rounded-full mx-auto -mt-20 flex items-center justify-center text-2xl font-bold text-white border-4 shadow-lg"
            style={{
              background: `linear-gradient(160deg, ${card.accent_color}, ${card.button_color})`,
              borderColor: card.bg_color,
            }}
          >
            {initials}
          </div>
        )}

        <h1 className="mt-4 text-2xl font-bold">{card.display_name}</h1>
        {(card.job_title || card.company_name) && (
          <p className="mt-1 text-sm opacity-70">
            {[card.job_title, card.company_name].filter(Boolean).join(' · ')}
          </p>
        )}
        {card.tagline && <p className="mt-3 text-sm opacity-80">{card.tagline}</p>}

        <div className="mt-6 space-y-2.5">
          <button
            onClick={onSaveContact}
            className="w-full flex items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-semibold text-white shadow-md"
            style={{
              background: `linear-gradient(90deg, ${card.accent_color}, ${card.button_color})`,
              color: card.button_text_color,
            }}
          >
            <UserPlus className="w-4 h-4" /> Save Contact
          </button>
          {card.booking_url && (
            <a
              href={card.booking_url}
              className="w-full flex items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-semibold border-2"
              style={{ borderColor: card.accent_color, color: card.accent_color }}
            >
              <CalendarDays className="w-4 h-4" /> Book a meeting
            </a>
          )}
        </div>

        <div className="mt-6 space-y-2 text-sm">
          {card.email && (
            <a href={`mailto:${card.email}`} className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Mail className="w-4 h-4" style={{ color: card.accent_color }} /> {card.email}
            </a>
          )}
          {card.phone && (
            <a href={`tel:${card.phone}`} className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Phone className="w-4 h-4" style={{ color: card.accent_color }} /> {card.phone}
            </a>
          )}
          {card.website && (
            <a href={card.website} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Globe className="w-4 h-4" style={{ color: card.accent_color }} /> {card.website.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>

        {Object.keys(card.social_links).length > 0 && (
          <div className="mt-5 flex justify-center flex-wrap gap-2 text-xs">
            {Object.entries(card.social_links).map(([label, url]) => (
              <a
                key={label}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1 rounded-full font-medium capitalize"
                style={{ background: `${card.accent_color}22`, color: card.accent_color }}
              >
                {label}
              </a>
            ))}
          </div>
        )}

        <button onClick={onShowQr} className="mt-7 inline-flex items-center gap-1.5 text-xs opacity-50 hover:opacity-90">
          <QrCode className="w-3.5 h-3.5" /> Share this card
        </button>
      </div>
    </div>
  )
}
