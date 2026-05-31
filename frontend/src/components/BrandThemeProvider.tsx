/**
 * BrandThemeProvider (Commit 26).
 *
 * Pulls the public branding payload once on mount and sets a handful
 * of CSS custom properties on :root so the configured brand color
 * propagates across the whole app — sidebar active state, primary
 * CTAs, links, etc. Works on both authenticated and unauthenticated
 * routes (the /branding/public endpoint requires no token).
 *
 * The provider is intentionally render-passthrough. It owns no UI of
 * its own; it just sets the variables and renders children. Children
 * pick up the colors via `var(--brand-primary)` etc.
 */
import { useEffect } from 'react'
import { usePublicBranding } from '@/hooks/useBranding'

// Defaults — match BrandingSettings model server_defaults so an
// unconfigured install still renders sensibly.
const DEFAULT_PRIMARY = '#2563eb'
const DEFAULT_ACCENT = '#f59e0b'

interface Props {
  children: React.ReactNode
}

export default function BrandThemeProvider({ children }: Props) {
  const { branding } = usePublicBranding()
  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--brand-primary', branding?.primary_color || DEFAULT_PRIMARY)
    root.style.setProperty('--brand-accent', branding?.accent_color || DEFAULT_ACCENT)
  }, [branding?.primary_color, branding?.accent_color])
  return <>{children}</>
}
