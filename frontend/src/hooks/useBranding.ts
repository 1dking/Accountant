import { useQuery } from '@tanstack/react-query'
import { brandingApi } from '@/api/branding'
import { getCompanySettings, getLogoUrl } from '@/api/settings'
import type { BrandingSettings } from '@/types/models'
import type { CompanySettings } from '@/api/settings'

const DEFAULT_NAME = 'O-Brain'

/** Branding for authenticated users — merges branding_settings + company_settings */
export function useBranding() {
  const { data: brandingData } = useQuery({
    queryKey: ['branding'],
    queryFn: () => brandingApi.get() as Promise<{ data: BrandingSettings | null }>,
  })

  const { data: companyData } = useQuery({
    queryKey: ['company-settings'],
    queryFn: getCompanySettings,
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
    queryFn: () => brandingApi.getPublic() as Promise<{ data: BrandingSettings | null }>,
  })

  const branding = data?.data ?? null
  const logoUrl = branding?.logo_url || null
  const logoDarkUrl = branding?.logo_dark_url || null

  return { logoUrl, logoDarkUrl, orgName: DEFAULT_NAME, branding }
}
