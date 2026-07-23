import { api } from './client'

export interface BusinessCard {
  id: string
  slug: string
  is_published: boolean
  template: 'classic' | 'modern' | 'minimal' | 'gradient' | 'split' | 'bold'
  display_name: string
  job_title: string | null
  company_name: string | null
  tagline: string | null
  email: string | null
  phone: string | null
  website: string | null
  social_links_json: string | null
  avatar_storage_path: string | null
  show_org_logo: boolean
  bg_color: string | null
  text_color: string | null
  accent_color: string | null
  button_color: string | null
  button_text_color: string | null
  font: string | null
  scheduling_calendar_id: string | null
  show_booking: boolean
  created_at: string
  updated_at: string
}

export interface PublicCard {
  slug: string
  template: 'classic' | 'modern' | 'minimal' | 'gradient' | 'split' | 'bold'
  display_name: string
  job_title: string | null
  company_name: string | null
  tagline: string | null
  email: string | null
  phone: string | null
  website: string | null
  social_links: Record<string, string>
  avatar_url: string | null
  logo_url: string | null
  bg_color: string
  text_color: string
  accent_color: string
  button_color: string
  button_text_color: string
  font: string
  booking_url: string | null
  wallet_available: { apple: boolean; google: boolean }
}

export interface CardAnalytics {
  total_views: number
  unique_visitors: number
  total_vcard_downloads: number
}

export const cardsApi = {
  getMyCard: () => api.get<{ data: BusinessCard }>('/cards/me'),
  getMyCardAnalytics: () => api.get<{ data: CardAnalytics }>('/cards/me/analytics'),
  updateMyCard: (data: Partial<BusinessCard>) => api.put<{ data: BusinessCard }>('/cards/me', data),
  checkSlug: (slug: string) =>
    api.get<{ data: { slug: string; available: boolean; reason: string | null } }>(
      `/cards/slug-check?slug=${encodeURIComponent(slug)}`
    ),
  uploadAvatar: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<{ data: BusinessCard }>('/cards/me/avatar', form)
  },
  getPublicCard: (slug: string) => api.get<{ data: PublicCard }>(`/cards/public/${slug}`),
}
