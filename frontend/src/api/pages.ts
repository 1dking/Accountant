import { api } from './client'

export const pagesApi = {
  // Pages CRUD
  list: (page = 1, pageSize = 50) =>
    api.get(`/pages?page=${page}&page_size=${pageSize}`),

  get: (id: string) => api.get(`/pages/${id}`),

  create: (data: {
    title: string; slug?: string; description?: string;
    style_preset?: string; primary_color?: string; font_family?: string;
    website_id?: string; page_order?: number;
  }) => api.post('/pages', data),

  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/pages/${id}`, data),

  delete: (id: string) => api.delete(`/pages/${id}`),

  publish: (id: string) => api.post(`/pages/${id}/publish`),

  // Versions
  listVersions: (pageId: string) => api.get(`/pages/${pageId}/versions`),

  restoreVersion: (pageId: string, versionId: string) =>
    api.post(`/pages/${pageId}/versions/${versionId}/restore`),

  // Analytics
  getAnalytics: (pageId: string, days = 30) =>
    api.get(`/pages/${pageId}/analytics?days=${days}`),

  // AI
  aiGenerate: (data: { prompt: string; style_preset?: string; primary_color?: string; font_family?: string; sections?: string[] }) =>
    api.post('/pages/ai/generate', data),

  aiRefine: (data: { page_id: string; instruction: string; section_index?: number }) =>
    api.post('/pages/ai/refine', data),

  aiChat: (data: { page_id: string; message: string }) =>
    api.post('/pages/ai/chat', data),

  // Style library
  getStylePresets: () => api.get('/pages/style-presets'),
  getSectionTemplates: () => api.get('/pages/section-templates'),

  // Websites
  listWebsites: () => api.get('/pages/websites'),
  createWebsite: (data: { name: string; slug?: string }) => api.post('/pages/websites', data),
  getWebsite: (id: string) => api.get(`/pages/websites/${id}`),
  updateWebsite: (id: string, data: Record<string, unknown>) => api.put(`/pages/websites/${id}`, data),
  deleteWebsite: (id: string) => api.delete(`/pages/websites/${id}`),
  getWebsitePages: (websiteId: string) => api.get(`/pages/websites/${websiteId}/pages`),

  // Video
  uploadVideo: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.upload('/pages/video/upload', formData)
  },
}
