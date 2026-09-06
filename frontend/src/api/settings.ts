import { api } from './client'

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export interface TaxRateInfo {
  id: string
  name: string
  rate: number
}

export interface CompanySettings {
  id: string
  company_name: string | null
  company_email: string | null
  company_phone: string | null
  company_website: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  zip_code: string | null
  country: string | null
  /** ISO-3166-2:CA — ON, BC, QC… Drives default GST/HST/PST/QST rates. */
  province: string | null
  /** CRA Business Number, 9 digits. */
  business_number: string | null
  /** GST/HST program account — usually BN + "RT0001". */
  gst_hst_number: string | null
  /** 1–12. */
  fiscal_year_end_month: number | null
  logo_storage_path: string | null
  default_tax_rate_id: string | null
  default_currency: string
  default_tax_rate: TaxRateInfo | null
}

export function getCompanySettings() {
  return api.get<ApiResponse<CompanySettings>>('/settings/company')
}

export function updateCompanySettings(data: Partial<CompanySettings>) {
  return api.put<ApiResponse<CompanySettings>>('/settings/company', data)
}

export function uploadLogo(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.upload<ApiResponse<CompanySettings>>('/settings/company/logo', formData)
}

export function deleteLogo() {
  return api.delete<ApiResponse<{ message: string }>>('/settings/company/logo')
}

// Logo URL is public (no auth needed)
export function getLogoUrl(): string {
  return '/api/settings/company/logo'
}
