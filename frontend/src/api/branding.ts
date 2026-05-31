import { api } from './client'

export const brandingApi = {
  get: () => api.get('/branding'),

  update: (data: Record<string, unknown>) =>
    api.put('/branding', data),

  getPublic: () => api.get('/branding/public'),

  /** Commit 27 — upload a brand logo file. Backend stores it in R2
   *  and writes the resulting public URL into BrandingSettings.logo_url. */
  uploadLogo: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.upload('/branding/logo', fd)
  },
}
