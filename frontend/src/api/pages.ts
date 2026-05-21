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

  // Conversational PRD-first generation (Pages v2 — Session 1).
  // Workflow: create session → submit prompt (Claude derives PRD) →
  // optionally re-prompt to iterate → approve → trigger generate →
  // poll session until status='complete' (or 'failed').
  aiCreateSession: () => api.post('/pages/ai/sessions'),
  aiGetSession: (sessionId: string) =>
    api.get(`/pages/ai/sessions/${sessionId}`),
  aiSubmitPrompt: (sessionId: string, prompt: string) =>
    api.post(`/pages/ai/sessions/${sessionId}/prompt`, { prompt }),
  aiApprovePrd: (sessionId: string) =>
    api.post(`/pages/ai/sessions/${sessionId}/approve`),
  aiTriggerGenerate: (sessionId: string) =>
    api.post(`/pages/ai/sessions/${sessionId}/generate`),
  aiRefineSection: (pageId: string, sectionIndex: number, instruction: string) =>
    api.post(`/pages/${pageId}/sections/${sectionIndex}/refine`, { instruction }),

  // Per-section CRUD (SectionEditor — Pages v2). All four endpoints
  // mutate sections_json in place and re-run compile_page so
  // html_content stays in sync with the structured source-of-truth.
  patchSection: (
    pageId: string,
    idx: number,
    data: {
      edited_html?: string | null
      style_overrides?: Record<string, unknown> | null
      media_overrides?: Record<string, string> | null
    } | Record<string, unknown>,
  ) => api.patch(`/pages/${pageId}/sections/${idx}`, data),
  duplicateSection: (pageId: string, idx: number) =>
    api.post(`/pages/${pageId}/sections/${idx}/duplicate`),
  deleteSection: (pageId: string, idx: number) =>
    api.delete(`/pages/${pageId}/sections/${idx}`),
  revertSection: (pageId: string, idx: number) =>
    api.post(`/pages/${pageId}/sections/${idx}/revert`),

  // Variant library (SectionEditor picker — Commit 2)
  listVariants: (category?: string) => {
    const q = category ? `?category=${encodeURIComponent(category)}` : ''
    return api.get(`/pages/variants${q}`)
  },
  addSection: (
    pageId: string,
    data: { category: string; variant_id: string; prop_overrides?: Record<string, unknown> },
    afterIdx?: number,
  ) => {
    const q = typeof afterIdx === 'number' ? `?after_idx=${afterIdx}` : ''
    return api.post(`/pages/${pageId}/sections${q}`, data)
  },
  changeVariant: (
    pageId: string,
    idx: number,
    data: { category: string; variant_id: string },
  ) => api.post(`/pages/${pageId}/sections/${idx}/change-variant`, data),

  reorderSections: (pageId: string, fromIndex: number, toIndex: number) =>
    api.patch(`/pages/${pageId}/sections/reorder`, {
      from_index: fromIndex,
      to_index: toIndex,
    }),

  // Media slots (SectionEditor — Commit 3)
  uploadMedia: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.upload('/pages/media/upload', fd)
  },

  // Static publish (Pages v2 — Session 2). Compiles sections to HTML +
  // uploads to R2 + flips page status to PUBLISHED. Idempotent: same
  // content hash short-circuits to was_unchanged=true.
  publishStatic: (id: string) =>
    api.post(`/pages/${id}/publish-static`),

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

  // Templates
  listTemplates: () => api.get('/pages/templates'),
  getTemplate: (id: string) => api.get(`/pages/templates/${id}`),
  createTemplate: (data: {
    name: string; description?: string; category_industry?: string;
    category_type?: string; html_content?: string; css_content?: string;
    scope?: string; source_page_id?: string;
  }) => api.post('/pages/templates', data),
  updateTemplate: (id: string, data: Record<string, unknown>) =>
    api.put(`/pages/templates/${id}`, data),
  deleteTemplate: (id: string) => api.delete(`/pages/templates/${id}`),
  createPageFromTemplate: (templateId: string, title: string, websiteId?: string, orgName?: string) => {
    const params = new URLSearchParams({ title })
    if (websiteId) params.set('website_id', websiteId)
    if (orgName) params.set('org_name', orgName)
    return api.post(`/pages/templates/${templateId}/create-page?${params.toString()}`)
  },

  // Video
  uploadVideo: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.upload('/pages/video/upload', formData)
  },

  // Update live page
  updateLive: (id: string) => api.post(`/pages/${id}/update-live`),

  // Custom domains
  listDomains: (pageId: string) => api.get(`/pages/${pageId}/domains`),
  addDomain: (pageId: string, domain: string) => api.post(`/pages/${pageId}/domains`, { domain }),
  verifyDomain: (domainId: string) => api.post(`/pages/domains/${domainId}/verify`),
  deleteDomain: (domainId: string) => api.delete(`/pages/domains/${domainId}`),

  // Split tests
  listSplitTests: (pageId: string) => api.get(`/pages/${pageId}/split-tests`),
  createSplitTest: (pageId: string, name: string) => api.post(`/pages/${pageId}/split-tests`, { name, page_id: pageId }),
  getSplitTest: (testId: string) => api.get(`/pages/split-tests/${testId}`),
  addVariation: (testId: string, data: { name: string; html_content?: string; css_content?: string; traffic_percentage?: number }) => api.post(`/pages/split-tests/${testId}/variations`, data),
  duplicateVariation: (testId: string, pageId: string) => api.post(`/pages/split-tests/${testId}/duplicate-variation?page_id=${pageId}`),
  startTest: (testId: string) => api.post(`/pages/split-tests/${testId}/start`),
  pauseTest: (testId: string) => api.post(`/pages/split-tests/${testId}/pause`),
  stopTest: (testId: string) => api.post(`/pages/split-tests/${testId}/stop`),
  declareWinner: (testId: string, variationId: string) => api.post(`/pages/split-tests/${testId}/declare-winner?variation_id=${variationId}`),
}