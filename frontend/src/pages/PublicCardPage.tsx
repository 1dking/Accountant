/**
 * Public digital business card — /c/:slug (no auth).
 *
 * One fetch (the server resolves palette/booking/logo), template
 * dispatch, vCard download via the backend endpoint (server sets the
 * attachment headers), QR share overlay, and a per-card PWA manifest:
 * the global O-Brain manifest <link> is swapped for this card's while
 * mounted so "Add to Home Screen" installs the card under the person's
 * name and colors, then restored on unmount.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { cardsApi } from '@/api/cards'
import ClassicCard from '@/components/cards/templates/ClassicCard'
import ModernCard from '@/components/cards/templates/ModernCard'
import MinimalCard from '@/components/cards/templates/MinimalCard'
import QrShareOverlay from '@/components/cards/QrShareOverlay'

const TEMPLATES = {
  classic: ClassicCard,
  modern: ModernCard,
  minimal: MinimalCard,
} as const

export default function PublicCardPage() {
  const { slug } = useParams<{ slug: string }>()
  const [showQr, setShowQr] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-card', slug],
    queryFn: () => cardsApi.getPublicCard(slug!),
    enabled: !!slug,
  })
  const card = data?.data

  // Per-card PWA manifest + theme color while mounted.
  useEffect(() => {
    if (!card) return
    const manifestLink = document.querySelector<HTMLLinkElement>('link[rel="manifest"]')
    const themeMeta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    const prevManifest = manifestLink?.href ?? null
    const prevTheme = themeMeta?.content ?? null

    if (manifestLink) manifestLink.href = `/api/cards/public/${card.slug}/manifest`
    if (themeMeta) themeMeta.content = card.bg_color
    document.title = card.display_name

    return () => {
      if (manifestLink && prevManifest) manifestLink.href = prevManifest
      if (themeMeta && prevTheme) themeMeta.content = prevTheme
      document.title = 'O-Brain'
    }
  }, [card])

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>
  }

  if (isError || !card) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <p className="text-sm text-gray-500">This card doesn't exist or isn't published.</p>
      </div>
    )
  }

  const Template = TEMPLATES[card.template] ?? ClassicCard
  const cardUrl = `${window.location.origin}/c/${card.slug}`

  return (
    <>
      <Template
        card={card}
        cardUrl={cardUrl}
        onSaveContact={() => {
          window.location.href = `/api/cards/public/${card.slug}/vcard`
        }}
        onShowQr={() => setShowQr(true)}
      />
      {showQr && (
        <QrShareOverlay url={cardUrl} displayName={card.display_name} onClose={() => setShowQr(false)} />
      )}
    </>
  )
}
