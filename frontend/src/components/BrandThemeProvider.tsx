/**
 * BrandThemeProvider (Commit 26; extended to apply the full theme set).
 *
 * Pulls the public branding payload once on mount and sets CSS custom
 * properties on :root so the configured brand identity propagates
 * across the whole app — sidebar active state, primary CTAs, links,
 * fonts, corner radius, etc. Works on both authenticated and
 * unauthenticated routes (the /branding/public endpoint requires no
 * token) for everything except custom_css, which the public endpoint
 * deliberately omits (backend/app/branding/schemas.py PublicBrandingResponse)
 * — injecting admin-authored CSS on public-facing pages (login, portal,
 * a future public business card) would let a compromised admin account
 * attack anonymous visitors. custom_css is fetched separately via the
 * authenticated endpoint and only applied once logged in.
 *
 * The provider is intentionally render-passthrough. It owns no UI of
 * its own; it just sets the variables/tags and renders children.
 * Children pick up the values via `var(--brand-primary)` etc.
 */
import { useEffect } from 'react'
import { usePublicBranding, useBranding } from '@/hooks/useBranding'
import { useAuthStore } from '@/stores/authStore'

// Defaults — match BrandingSettings model server_defaults so an
// unconfigured install still renders sensibly.
const DEFAULT_PRIMARY = '#2563eb'
const DEFAULT_SECONDARY = '#64748b'
const DEFAULT_ACCENT = '#f59e0b'
const DEFAULT_FONT_HEADING = 'Inter'
const DEFAULT_FONT_BODY = 'Inter'
const DEFAULT_RADIUS = '8px'

// Common system/web-safe font names that must NOT be requested from
// Google Fonts (the request would just fail silently, but there's no
// reason to make it).
const SYSTEM_FONT_KEYWORDS = new Set([
  'system-ui', 'sans-serif', 'serif', 'monospace', 'ui-sans-serif', 'ui-serif', 'ui-monospace',
  'arial', 'helvetica', 'helvetica neue', 'georgia', 'times new roman', 'times',
  'courier new', 'courier', 'verdana', 'tahoma', 'trebuchet ms', 'segoe ui', 'roboto mono',
])

function isGoogleFontCandidate(name: string): boolean {
  const trimmed = name.trim()
  return trimmed.length > 0 && !SYSTEM_FONT_KEYWORDS.has(trimmed.toLowerCase())
}

function quoteFontFamily(name: string): string {
  // A bare CSS custom property value needs quoting when it contains
  // spaces so it's treated as one family name, not several.
  return /\s/.test(name.trim()) ? `"${name.trim()}"` : name.trim()
}

interface Props {
  children: React.ReactNode
}

export default function BrandThemeProvider({ children }: Props) {
  const { branding } = usePublicBranding()
  const { isAuthenticated } = useAuthStore()
  const { branding: privateBranding } = useBranding(isAuthenticated)

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--brand-primary', branding?.primary_color || DEFAULT_PRIMARY)
    root.style.setProperty('--brand-secondary', branding?.secondary_color || DEFAULT_SECONDARY)
    root.style.setProperty('--brand-accent', branding?.accent_color || DEFAULT_ACCENT)
    const fontHeading = branding?.font_heading || DEFAULT_FONT_HEADING
    const fontBody = branding?.font_body || DEFAULT_FONT_BODY
    root.style.setProperty('--brand-font-heading', `${quoteFontFamily(fontHeading)}, ui-sans-serif, sans-serif`)
    root.style.setProperty('--brand-font-body', `${quoteFontFamily(fontBody)}, ui-sans-serif, sans-serif`)
    root.style.setProperty('--brand-radius', branding?.border_radius || DEFAULT_RADIUS)
  }, [
    branding?.primary_color,
    branding?.secondary_color,
    branding?.accent_color,
    branding?.font_heading,
    branding?.font_body,
    branding?.border_radius,
  ])

  // Google Fonts loader — one managed <link>, rebuilt whenever the
  // chosen fonts change. Skipped entirely for system/web-safe fonts.
  useEffect(() => {
    const families = Array.from(
      new Set(
        [branding?.font_heading || DEFAULT_FONT_HEADING, branding?.font_body || DEFAULT_FONT_BODY]
          .filter(isGoogleFontCandidate)
      )
    )

    const existing = document.getElementById('brand-google-fonts')
    if (families.length === 0) {
      existing?.remove()
      return
    }

    const href = `https://fonts.googleapis.com/css2?${families
      .map((f) => `family=${encodeURIComponent(f.trim()).replace(/%20/g, '+')}:wght@400;500;600;700`)
      .join('&')}&display=swap`

    let link = existing as HTMLLinkElement | null
    if (!link) {
      link = document.createElement('link')
      link.id = 'brand-google-fonts'
      link.rel = 'stylesheet'
      document.head.appendChild(link)
    }
    if (link.href !== href) {
      link.href = href
    }
  }, [branding?.font_heading, branding?.font_body])

  // custom_css — authenticated surfaces only (see docstring above).
  useEffect(() => {
    const styleId = 'brand-custom-css'
    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null
    const css = isAuthenticated ? privateBranding?.custom_css : null

    if (!css) {
      styleEl?.remove()
      return
    }
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = styleId
      document.head.appendChild(styleEl)
    }
    styleEl.textContent = css
  }, [isAuthenticated, privateBranding?.custom_css])

  return <>{children}</>
}
