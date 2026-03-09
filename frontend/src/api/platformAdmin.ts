import { api } from './client'

export const platformAdminApi = {
  // Dashboard
  getDashboard: () => api.get('/platform-admin/dashboard'),

  // Feature flags
  listFeatureFlags: () => api.get('/platform-admin/feature-flags'),
  createFeatureFlag: (data: { key: string; name: string; description?: string; enabled?: boolean; category?: string }) =>
    api.post('/platform-admin/feature-flags', data),
  updateFeatureFlag: (key: string, data: { enabled?: boolean; name?: string; description?: string }) =>
    api.put(`/platform-admin/feature-flags/${key}`, data),
  deleteFeatureFlag: (key: string) => api.delete(`/platform-admin/feature-flags/${key}`),

  // Platform settings (pricing, limits)
  listSettings: (category?: string) =>
    api.get(`/platform-admin/settings${category ? `?category=${category}` : ''}`),
  createSetting: (data: { key: string; value?: string; category?: string; description?: string; value_type?: string }) =>
    api.post('/platform-admin/settings', data),
  updateSetting: (key: string, data: { value?: string; description?: string }) =>
    api.put(`/platform-admin/settings/${key}`, data),

  // Public pricing (any authenticated user)
  getPricing: () => api.get<{ data: Record<string, string> }>('/platform-admin/pricing'),

  // Health
  getHealth: () => api.get('/platform-admin/health'),

  // Errors
  listErrors: (params?: { level?: string; resolved?: boolean; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.level) searchParams.set('level', params.level)
    if (params?.resolved !== undefined) searchParams.set('resolved', String(params.resolved))
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.page_size) searchParams.set('page_size', String(params.page_size))
    return api.get(`/platform-admin/errors?${searchParams.toString()}`)
  },
  resolveError: (errorId: string) => api.post(`/platform-admin/errors/${errorId}/resolve`),

  // Users
  listUsers: (params?: { search?: string; role?: string; is_active?: boolean; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.search) searchParams.set('search', params.search)
    if (params?.role) searchParams.set('role', params.role)
    if (params?.is_active !== undefined) searchParams.set('is_active', String(params.is_active))
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.page_size) searchParams.set('page_size', String(params.page_size))
    return api.get(`/platform-admin/users?${searchParams.toString()}`)
  },
  getUserDetail: (userId: string) => api.get(`/platform-admin/users/${userId}`),
  impersonateUser: (userId: string) => api.post(`/platform-admin/users/${userId}/impersonate`),

  // Activity log
  getActivityLog: (params?: { user_id?: string; action?: string; resource_type?: string; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.user_id) searchParams.set('user_id', params.user_id)
    if (params?.action) searchParams.set('action', params.action)
    if (params?.resource_type) searchParams.set('resource_type', params.resource_type)
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.page_size) searchParams.set('page_size', String(params.page_size))
    return api.get(`/platform-admin/activity?${searchParams.toString()}`)
  },

  // Sessions
  listSessions: () => api.get('/platform-admin/sessions'),
  revokeSession: (sessionId: string) => api.post(`/platform-admin/sessions/${sessionId}/revoke`),
  revokeUserSessions: (userId: string) => api.post(`/platform-admin/users/${userId}/revoke-sessions`),

  // API keys
  listApiKeys: () => api.get('/platform-admin/api-keys'),
  saveApiKeys: (integration: string, config: Record<string, string>) =>
    api.put(`/platform-admin/api-keys/${integration}`, { config }),
  deleteApiKeys: (integration: string) =>
    api.delete(`/platform-admin/api-keys/${integration}`),
  testApiConnection: (integration: string) =>
    api.post(`/platform-admin/api-keys/${integration}/test`),

  // Organizations
  listOrganizations: (params?: { search?: string; plan?: string; is_active?: boolean; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.search) searchParams.set('search', params.search)
    if (params?.plan) searchParams.set('plan', params.plan)
    if (params?.is_active !== undefined) searchParams.set('is_active', String(params.is_active))
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.page_size) searchParams.set('page_size', String(params.page_size))
    return api.get(`/platform-admin/organizations?${searchParams.toString()}`)
  },
  getOrganization: (orgId: string) => api.get(`/platform-admin/organizations/${orgId}`),
  createOrganization: (data: { name: string; slug: string; owner_id: string; plan?: string; max_users?: number; max_storage_gb?: number; notes?: string }) =>
    api.post('/platform-admin/organizations', data),
  updateOrganization: (orgId: string, data: Record<string, unknown>) =>
    api.put(`/platform-admin/organizations/${orgId}`, data),
  deleteOrganization: (orgId: string) => api.delete(`/platform-admin/organizations/${orgId}`),

  // Org feature overrides
  setOrgFeatureOverride: (orgId: string, featureKey: string, enabled: boolean) =>
    api.put(`/platform-admin/organizations/${orgId}/features/${featureKey}`, { feature_key: featureKey, enabled }),
  deleteOrgFeatureOverride: (orgId: string, featureKey: string) =>
    api.delete(`/platform-admin/organizations/${orgId}/features/${featureKey}`),

  // Org setting overrides
  setOrgSettingOverride: (orgId: string, settingKey: string, value: string) =>
    api.put(`/platform-admin/organizations/${orgId}/settings/${settingKey}`, { setting_key: settingKey, value }),
  deleteOrgSettingOverride: (orgId: string, settingKey: string) =>
    api.delete(`/platform-admin/organizations/${orgId}/settings/${settingKey}`),

  // Org members
  addOrgMember: (orgId: string, userId: string) =>
    api.post(`/platform-admin/organizations/${orgId}/members`, { user_id: userId }),
  removeOrgMember: (orgId: string, userId: string) =>
    api.delete(`/platform-admin/organizations/${orgId}/members/${userId}`),
}
