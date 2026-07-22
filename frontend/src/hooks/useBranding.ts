import { useQuery } from '@tanstack/react-query'
import { brandingApi } from '@/api/branding'
import { getCompanySettings, getLogoUrl } from '@/api/settings'
import type { BrandingSettings } from '@/types/models'
import type { CompanySettings } from '@/api/settings'

const DEFAULT_NAME = 'O-Brain'

/**
 * Branding for authenticated users — merges branding_settings + company_settings.
 *
 * `enabled` gates both underlying queries (default true). Callers that
 * may render while logged out — e.g. BrandThemeProvider, mounted at the
 * app root for every route — must pass `isAuthenticated` explicitly:
 * the authenticated /branding endpoint 401s without a token, and the
 * api client treats any 401 as "redirect to /login", which would loop
 * on public pages if this query ran unconditionally.
 */
export function useBranding(enabled: boolean = true) {
  const { data: brandingData } = useQuery({
    queryKey: ['branding'],
    queryFn: () => brandingApi.get() as Promise<{ data: BrandingSettings | null }>,
    enabled,
  })

  const { data: companyData } = useQuery({
    queryKey: ['company-settings'],
    queryFn: getCompanySettings,
    enabled,
  })

  const branding = brandingData?.data ?? null
  const company: CompanySettings | null = (companyData as any)?.data ?? null

  // Logo priority: branding logo_url > company uploaded logo > null
  const logoUrl = branding?.logo_url || (company?.logo_storage_path ? getLogoUrl() : null)
  const logoDarkUrl = branding?.logo_dark_url || null
  const orgName = company?.company_name || DEFAULT_NAME

  return { logoUrl, logoDarkUrl, orgName, branding, company }
}

/** Branding for public pages (login, portal) — no auth required */
export function usePublicBranding() {
  const { data } = useQuery({
    queryKey: ['branding-public'],
    queryFn: () => brandingApi.getPublic() as Promise<{ data: (BrandingSettings & { org_name?: string | null }) | null }>,
  })

  const branding = data?.data ?? null
  const logoUrl = branding?.logo_url || null
  const logoDarkUrl = branding?.logo_dark_url || null
  // Commit 25 — backend now folds CompanySettings.company_name into
  // the public branding payload, so guest/login surfaces can show the
  // real org name instead of the hardcoded fallback.
  const orgName = branding?.org_name || DEFAULT_NAME

  return { logoUrl, logoDarkUrl, orgName, branding }
}
