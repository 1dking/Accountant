import { api } from './client'

export const brandingApi = {
  get: () => api.get('/branding'),

  update: (data: Record<string, unknown>) =>
    api.put('/branding', data),

  getPublic: () => api.get('/branding/public'),
}
