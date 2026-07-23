import { Mail, Phone, Globe, CalendarDays, QrCode, UserPlus, Wallet } from 'lucide-react'
import type { CardTemplateProps } from '../types'

/** Classic — centered avatar, stacked action buttons (Arivio classic.tsx). */
export default function ClassicCard({
  card,
  onSaveContact,
  onShowQr,
  onAddAppleWallet,
  onAddGoogleWallet,
}: CardTemplateProps) {
  const initials = card.display_name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div
      className="min-h-screen flex flex-col items-center px-6 py-10"
      style={{ background: card.bg_color, color: card.text_color, fontFamily: card.font }}
    >
      <div className="w-full max-w-sm text-center">
        {card.logo_url && (
          <img src={card.logo_url} alt="" className="h-8 mx-auto mb-6 object-contain" />
        )}

        {card.avatar_url ? (
          <img
            src={card.avatar_url}
            alt={card.display_name}
            className="w-28 h-28 rounded-full object-cover mx-auto border-4"
            style={{ borderColor: card.accent_color }}
          />
        ) : (
          <div
            className="w-28 h-28 rounded-full mx-auto flex items-center justify-center text-3xl font-bold text-white"
            style={{ background: card.accent_color }}
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
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold"
            style={{ background: card.button_color, color: card.button_text_color }}
          >
            <UserPlus className="w-4 h-4" /> Save Contact
          </button>
          {card.booking_url && (
            <a
              href={card.booking_url}
              className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold border"
              style={{ borderColor: card.accent_color, color: card.accent_color }}
            >
              <CalendarDays className="w-4 h-4" /> Book a meeting
            </a>
          )}
          {(onAddAppleWallet || onAddGoogleWallet) && (
            <div className="flex gap-2">
              {onAddAppleWallet && (
                <button
                  onClick={onAddAppleWallet}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-xs font-semibold bg-black text-white"
                >
                  <Wallet className="w-3.5 h-3.5" /> Apple Wallet
                </button>
              )}
              {onAddGoogleWallet && (
                <button
                  onClick={onAddGoogleWallet}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-xs font-semibold border border-gray-800 text-gray-900 bg-white"
                >
                  <Wallet className="w-3.5 h-3.5" /> Google Wallet
                </button>
              )}
            </div>
          )}
        </div>

        <div className="mt-6 space-y-2 text-sm">
          {card.email && (
            <a href={`mailto:${card.email}`} className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Mail className="w-4 h-4" /> {card.email}
            </a>
          )}
          {card.phone && (
            <a href={`tel:${card.phone}`} className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Phone className="w-4 h-4" /> {card.phone}
            </a>
          )}
          {card.website && (
            <a href={card.website} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 opacity-80 hover:opacity-100">
              <Globe className="w-4 h-4" /> {card.website.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>

        {Object.keys(card.social_links).length > 0 && (
          <div className="mt-5 flex justify-center gap-4 text-sm">
            {Object.entries(card.social_links).map(([label, url]) => (
              <a key={label} href={url} target="_blank" rel="noreferrer" className="underline opacity-70 hover:opacity-100 capitalize">
                {label}
              </a>
            ))}
          </div>
        )}

        <button onClick={onShowQr} className="mt-8 inline-flex items-center gap-1.5 text-xs opacity-50 hover:opacity-90">
          <QrCode className="w-3.5 h-3.5" /> Share this card
        </button>
      </div>
    </div>
  )
}
