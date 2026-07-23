import { Mail, Phone, Globe, CalendarDays, QrCode, UserPlus } from 'lucide-react'
import type { CardTemplateProps } from '../types'

/** Bold — oversized poster typography with a thick accent rule. */
export default function BoldCard({ card, onSaveContact, onShowQr }: CardTemplateProps) {
  const [firstName, ...rest] = card.display_name.split(' ')
  const lastName = rest.join(' ')

  return (
    <div
      className="min-h-screen flex flex-col justify-center px-7 py-12"
      style={{ background: card.bg_color, color: card.text_color, fontFamily: card.font }}
    >
      <div className="w-full max-w-sm mx-auto">
        {card.logo_url && <img src={card.logo_url} alt="" className="h-7 mb-8 object-contain" />}

        <div className="h-2 w-16 mb-6 rounded-full" style={{ background: card.accent_color }} />

        <h1 className="text-5xl font-extrabold leading-[1.05] tracking-tight">
          {firstName}
          {lastName && (
            <>
              <br />
              <span style={{ color: card.accent_color }}>{lastName}</span>
            </>
          )}
        </h1>

        {(card.job_title || card.company_name) && (
          <p className="mt-4 text-sm font-semibold uppercase tracking-widest opacity-60">
            {[card.job_title, card.company_name].filter(Boolean).join(' — ')}
          </p>
        )}
        {card.tagline && <p className="mt-4 text-base leading-relaxed opacity-80">{card.tagline}</p>}

        {card.avatar_url && (
          <img
            src={card.avatar_url}
            alt={card.display_name}
            className="mt-6 w-20 h-20 rounded-2xl object-cover border-2"
            style={{ borderColor: card.accent_color }}
          />
        )}

        <div className="mt-8 space-y-2.5">
          <button
            onClick={onSaveContact}
            className="w-full flex items-center justify-center gap-2 px-4 py-4 text-sm font-bold uppercase tracking-wider"
            style={{ background: card.button_color, color: card.button_text_color }}
          >
            <UserPlus className="w-4 h-4" /> Save Contact
          </button>
          {card.booking_url && (
            <a
              href={card.booking_url}
              className="w-full flex items-center justify-center gap-2 px-4 py-4 text-sm font-bold uppercase tracking-wider border-2"
              style={{ borderColor: card.text_color, color: card.text_color }}
            >
              <CalendarDays className="w-4 h-4" /> Book a meeting
            </a>
          )}
        </div>

        <div className="mt-8 space-y-2.5 text-sm font-medium">
          {card.email && (
            <a href={`mailto:${card.email}`} className="flex items-center gap-3 opacity-80 hover:opacity-100">
              <Mail className="w-4 h-4" style={{ color: card.accent_color }} /> {card.email}
            </a>
          )}
          {card.phone && (
            <a href={`tel:${card.phone}`} className="flex items-center gap-3 opacity-80 hover:opacity-100">
              <Phone className="w-4 h-4" style={{ color: card.accent_color }} /> {card.phone}
            </a>
          )}
          {card.website && (
            <a href={card.website} target="_blank" rel="noreferrer" className="flex items-center gap-3 opacity-80 hover:opacity-100">
              <Globe className="w-4 h-4" style={{ color: card.accent_color }} /> {card.website.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>

        {Object.keys(card.social_links).length > 0 && (
          <div className="mt-6 flex flex-wrap gap-x-5 gap-y-1 text-sm font-bold uppercase tracking-wide">
            {Object.entries(card.social_links).map(([label, url]) => (
              <a
                key={label}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="underline decoration-4 underline-offset-4 capitalize"
                style={{ textDecorationColor: card.accent_color }}
              >
                {label}
              </a>
            ))}
          </div>
        )}

        <button onClick={onShowQr} className="mt-10 inline-flex items-center gap-1.5 text-xs opacity-50 hover:opacity-90">
          <QrCode className="w-3.5 h-3.5" /> Share this card
        </button>
      </div>
    </div>
  )
}
