import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pagesApi } from '@/api/pages'
import { toast } from 'sonner'
import {
  Plus,
  Send,
  Globe,
  FileText,
  Eye,
  Code,
  Paintbrush,
  BarChart3,
  Loader2,
  Monitor,
  Tablet,
  Smartphone,
  Save,
  Upload,
  ArrowLeft,
  Trash2,
  ExternalLink,
  Settings,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Bookmark,
  LayoutTemplate,
  Search,
  Brain,
  Sparkles,
  History,
  RotateCcw,
  Check,
  Copy,
  FlaskConical,
  Play,
  Pause,
  Square,
  Trophy,
  Link,
  Shield,
  Clock,
  Columns2,
} from 'lucide-react'
import VisualEditor from '@/components/pages/VisualEditor'
import AnalyticsDashboard from '@/components/pages/AnalyticsDashboard'
import TrackingPixelsSettings from '@/components/pages/TrackingPixelsSettings'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PageItem {
  id: string
  title: string
  slug: string
  status: string
  is_homepage: boolean
  website_id?: string
  page_order: number
  created_at: string
  updated_at: string
}

interface PageDetail extends PageItem {
  html_content?: string
  css_content?: string
  js_content?: string
  tracking_pixels_json?: string
  chat_history_json?: string
  style_preset?: string
  primary_color?: string
  font_family?: string
  created_by: string
  meta_title?: string
  meta_description?: string
  live_html_content?: string
  live_css_content?: string
  auto_publish?: boolean
  next_page_id?: string
  page_purpose?: string
}

interface WebsiteItem {
  id: string
  name: string
  slug: string
  domain?: string
  is_published: boolean
  page_count: number
  created_at: string
  updated_at: string
}

interface TemplateItem {
  id: string
  name: string
  description?: string
  category_industry?: string
  category_type?: string
  thumbnail_url?: string
  scope: string
  is_active: boolean
  created_at: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface VersionItem {
  id: string
  page_id: string
  version_number: number
  html_content?: string
  css_content?: string
  change_summary?: string
  created_by: string
  created_at: string
}

interface DomainItem {
  id: string
  page_id?: string
  website_id?: string
  domain: string
  domain_type: string
  dns_record_type: string
  dns_target?: string
  dns_verified: boolean
  ssl_status: string
  ssl_expires_at?: string
  verified_at?: string
  created_at: string
}

interface SplitTestItem {
  id: string
  page_id: string
  name: string
  status: string
  auto_optimize: boolean
  started_at?: string
  completed_at?: string
  winner_variation_id?: string
  created_by: string
  created_at: string
  variations: SplitVariation[]
}

interface SplitVariation {
  id: string
  test_id: string
  name: string
  html_content?: string
  css_content?: string
  traffic_percentage: number
  visitors: number
  conversions: number
  created_at: string
}

type View = 'list' | 'edit' | 'website-edit'
type EditorTab = 'preview' | 'visual' | 'html' | 'css' | 'analytics' | 'settings'
type ResponsiveSize = 'desktop' | 'tablet' | 'mobile'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function unwrap<T>(res: unknown): T {
  if (res == null) return undefined as unknown as T
  const outer = (res as any).data
  if (outer == null) return res as T
  return outer?.data ?? outer ?? res
}

function parseChatHistory(json?: string | null): ChatMessage[] {
  if (!json) return []
  try {
    const parsed = JSON.parse(json)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const RESPONSIVE_WIDTHS: Record<ResponsiveSize, string> = {
  desktop: '100%',
  tablet: '768px',
  mobile: '375px',
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PageBuilderPage() {
  const queryClient = useQueryClient()

  // Navigation state
  const [view, setView] = useState<View>('list')
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null)
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string | null>(null)

  // Modals
  const [showCreatePage, setShowCreatePage] = useState(false)
  const [showCreateWebsite, setShowCreateWebsite] = useState(false)
  const [createPageTitle, setCreatePageTitle] = useState('')
  const [createWebsiteName, setCreateWebsiteName] = useState('')

  // Editor state
  const [editHtml, setEditHtml] = useState('')
  const [editCss, setEditCss] = useState('')
  const [activeTab, setActiveTab] = useState<EditorTab>('preview')
  const [responsiveSize, setResponsiveSize] = useState<ResponsiveSize>('desktop')
  const [chatCollapsed, setChatCollapsed] = useState(false)

  // Chat state
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Draft/save state
  const [draftSaved, setDraftSaved] = useState(false)
  const [hasUnpublishedChanges, setHasUnpublishedChanges] = useState(false)

  // Template state
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDesc, setTemplateDesc] = useState('')
  const [templateIndustry, setTemplateIndustry] = useState('')
  const [templateType, setTemplateType] = useState('')
  const [showTemplateBrowser, setShowTemplateBrowser] = useState(false)
  const [templateSearch, setTemplateSearch] = useState('')
  const [templateFilterIndustry, setTemplateFilterIndustry] = useState('')
  const [previewTemplateId, setPreviewTemplateId] = useState<string | null>(null)
  const [previewTemplateHtml, setPreviewTemplateHtml] = useState<string>('')
  const [previewTemplateName, setPreviewTemplateName] = useState<string>('')
  const [previewDevice, setPreviewDevice] = useState<'desktop' | 'tablet' | 'mobile'>('desktop')
  const [loadingPreview, setLoadingPreview] = useState(false)

  // Version history state
  const [compareVersionId, setCompareVersionId] = useState<string | null>(null)
  const [compareHtml, setCompareHtml] = useState('')

  // Custom domain state
  const [newDomain, setNewDomain] = useState('')

  // Split test state
  const [showCreateTest, setShowCreateTest] = useState(false)
  const [newTestName, setNewTestName] = useState('')

  // Auto-save
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const htmlRef = useRef(editHtml)
  const cssRef = useRef(editCss)
  htmlRef.current = editHtml
  cssRef.current = editCss

  // -------------------------------------------------------------------------
  // Queries
  // -------------------------------------------------------------------------

  const { data: pagesRes, isLoading: pagesLoading } = useQuery({
    queryKey: ['pages'],
    queryFn: () => pagesApi.list(),
  })

  const { data: websitesRes, isLoading: websitesLoading } = useQuery({
    queryKey: ['websites'],
    queryFn: () => pagesApi.listWebsites(),
  })

  const { data: pageDetailRes, isLoading: pageDetailLoading } = useQuery({
    queryKey: ['page', selectedPageId],
    queryFn: () => pagesApi.get(selectedPageId!),
    enabled: !!selectedPageId,
  })

  const { data: websitePagesRes } = useQuery({
    queryKey: ['website-pages', selectedWebsiteId],
    queryFn: () => pagesApi.getWebsitePages(selectedWebsiteId!),
    enabled: !!selectedWebsiteId && view === 'website-edit',
  })

  const { data: templatesRes } = useQuery({
    queryKey: ['page-templates'],
    queryFn: () => pagesApi.listTemplates(),
  })

  const { data: versionsRes } = useQuery({
    queryKey: ['page-versions', selectedPageId],
    queryFn: () => pagesApi.listVersions(selectedPageId!),
    enabled: !!selectedPageId,
  })

  const { data: domainsRes } = useQuery({
    queryKey: ['page-domains', selectedPageId],
    queryFn: () => pagesApi.listDomains(selectedPageId!),
    enabled: !!selectedPageId && activeTab === 'settings',
  })

  const { data: splitTestsRes } = useQuery({
    queryKey: ['split-tests', selectedPageId],
    queryFn: () => pagesApi.listSplitTests(selectedPageId!),
    enabled: !!selectedPageId,
  })

  const pages: PageItem[] = Array.isArray(unwrap(pagesRes)) ? unwrap<PageItem[]>(pagesRes) : []
  const websites: WebsiteItem[] = Array.isArray(unwrap(websitesRes)) ? unwrap<WebsiteItem[]>(websitesRes) : []
  const detail: PageDetail | null = unwrap<PageDetail>(pageDetailRes) ?? null
  const websitePages: PageItem[] = Array.isArray(unwrap(websitePagesRes)) ? unwrap<PageItem[]>(websitePagesRes) : []
  const templates: TemplateItem[] = Array.isArray(unwrap(templatesRes)) ? unwrap<TemplateItem[]>(templatesRes) : []
  const versions: VersionItem[] = Array.isArray(unwrap(versionsRes)) ? unwrap<VersionItem[]>(versionsRes) : []
  const domains: DomainItem[] = Array.isArray(unwrap(domainsRes)) ? unwrap<DomainItem[]>(domainsRes) : []
  const splitTests: SplitTestItem[] = Array.isArray(unwrap(splitTestsRes)) ? unwrap<SplitTestItem[]>(splitTestsRes) : []

  const standalonePages = pages.filter((p) => !p.website_id)
  const isPublished = detail?.status === 'published'

  // -------------------------------------------------------------------------
  // Sync editor state when page detail loads
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (detail) {
      setEditHtml(detail.html_content || '')
      setEditCss(detail.css_content || '')
      setChatMessages(parseChatHistory(detail.chat_history_json))
      // Check for unpublished changes
      if (isPublished && detail.live_html_content) {
        setHasUnpublishedChanges(
          detail.html_content !== detail.live_html_content ||
          detail.css_content !== detail.live_css_content
        )
      } else {
        setHasUnpublishedChanges(false)
      }
    }
  }, [detail?.id, detail?.html_content, detail?.css_content, detail?.chat_history_json])

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // -------------------------------------------------------------------------
  // Mutations
  // -------------------------------------------------------------------------

  const createPageMutation = useMutation({
    mutationFn: (data: { title: string; website_id?: string }) =>
      pagesApi.create(data),
    onSuccess: (res) => {
      const created = unwrap<PageDetail>(res)
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      if (created?.id) {
        setSelectedPageId(created.id)
        if (created.website_id) {
          setSelectedWebsiteId(created.website_id)
          queryClient.invalidateQueries({ queryKey: ['website-pages', created.website_id] })
          setView('website-edit')
        } else {
          setView('edit')
        }
      }
      setShowCreatePage(false)
      setCreatePageTitle('')
      toast.success('Page created')
    },
    onError: () => toast.error('Failed to create page'),
  })

  const createWebsiteMutation = useMutation({
    mutationFn: (data: { name: string }) => pagesApi.createWebsite(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      setShowCreateWebsite(false)
      setCreateWebsiteName('')
      toast.success('Website created')
    },
    onError: () => toast.error('Failed to create website'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      pagesApi.update(id, data),
    onSuccess: () => {
      setDraftSaved(true)
      setTimeout(() => setDraftSaved(false), 3000)
      if (isPublished) setHasUnpublishedChanges(true)
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
    },
  })

  const publishMutation = useMutation({
    mutationFn: (id: string) => pagesApi.publish(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      queryClient.invalidateQueries({ queryKey: ['page-versions', selectedPageId] })
      setHasUnpublishedChanges(false)
      toast.success('Page published!')
    },
    onError: () => toast.error('Failed to publish page'),
  })

  const updateLiveMutation = useMutation({
    mutationFn: (id: string) => pagesApi.updateLive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      queryClient.invalidateQueries({ queryKey: ['page-versions', selectedPageId] })
      setHasUnpublishedChanges(false)
      toast.success('Live site updated!')
    },
    onError: () => toast.error('Failed to update live site'),
  })

  const deletePageMutation = useMutation({
    mutationFn: (id: string) => pagesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      if (selectedWebsiteId) {
        queryClient.invalidateQueries({ queryKey: ['website-pages', selectedWebsiteId] })
      }
      toast.success('Page deleted')
    },
    onError: () => toast.error('Failed to delete page'),
  })

  const deleteWebsiteMutation = useMutation({
    mutationFn: (id: string) => pagesApi.deleteWebsite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      toast.success('Website deleted')
    },
    onError: () => toast.error('Failed to delete website'),
  })

  const aiChatMutation = useMutation({
    mutationFn: (data: { page_id: string; message: string }) =>
      pagesApi.aiChat(data),
    onSuccess: (res) => {
      const result = unwrap<{
        response?: string
        html_content?: string
        css_content?: string
      }>(res)
      // Update preview with generated HTML/CSS
      if (result?.html_content !== undefined) setEditHtml(result.html_content || '')
      if (result?.css_content !== undefined) setEditCss(result.css_content || '')
      // Show only conversational text in chat (strip any stray HTML/code blocks)
      if (result?.response) {
        let chatText = result.response
        chatText = chatText.replace(/```html[\s\S]*?```/g, '').replace(/```css[\s\S]*?```/g, '').replace(/```[\s\S]*?```/g, '').trim()
        if (!chatText) chatText = 'Your page is ready. Check the preview.'
        setChatMessages((prev) => [...prev, { role: 'assistant', content: chatText }])
      } else {
        setChatMessages((prev) => [...prev, { role: 'assistant', content: 'Your page is ready. Check the preview.' }])
      }
      // Auto-switch to preview tab to show the result
      setActiveTab('preview')
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
    },
    onError: () => {
      toast.error('AI chat failed')
      setChatMessages((prev) => prev.filter((m) => m.content !== '...'))
    },
  })

  const saveTemplateMutation = useMutation({
    mutationFn: (data: {
      name: string; description?: string; category_industry?: string;
      category_type?: string; source_page_id?: string; scope?: string;
    }) => pagesApi.createTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-templates'] })
      setShowSaveTemplate(false)
      setTemplateName('')
      setTemplateDesc('')
      setTemplateIndustry('')
      setTemplateType('')
      toast.success('Template saved!')
    },
    onError: () => toast.error('Failed to save template'),
  })

  const createFromTemplateMutation = useMutation({
    mutationFn: (data: { templateId: string; title: string; websiteId?: string }) =>
      pagesApi.createPageFromTemplate(data.templateId, data.title, data.websiteId),
    onSuccess: (res) => {
      const created = unwrap<PageDetail>(res)
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      if (created?.id) {
        setSelectedPageId(created.id)
        if (created.website_id) {
          setSelectedWebsiteId(created.website_id)
          queryClient.invalidateQueries({ queryKey: ['website-pages', created.website_id] })
          setView('website-edit')
        } else {
          setView('edit')
        }
      }
      setShowTemplateBrowser(false)
      toast.success('Page created from template')
    },
    onError: () => toast.error('Failed to create page from template'),
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: (id: string) => pagesApi.deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-templates'] })
      toast.success('Template deleted')
    },
    onError: () => toast.error('Failed to delete template'),
  })

  const restoreVersionMutation = useMutation({
    mutationFn: ({ pageId, versionId }: { pageId: string; versionId: string }) =>
      pagesApi.restoreVersion(pageId, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      queryClient.invalidateQueries({ queryKey: ['page-versions', selectedPageId] })
      toast.success('Version restored')
    },
    onError: () => toast.error('Failed to restore version'),
  })

  const addDomainMutation = useMutation({
    mutationFn: ({ pageId, domain }: { pageId: string; domain: string }) =>
      pagesApi.addDomain(pageId, domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-domains', selectedPageId] })
      setNewDomain('')
      toast.success('Domain added')
    },
    onError: () => toast.error('Failed to add domain'),
  })

  const verifyDomainMutation = useMutation({
    mutationFn: (domainId: string) => pagesApi.verifyDomain(domainId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-domains', selectedPageId] })
      toast.success('Domain verification updated')
    },
  })

  const deleteDomainMutation = useMutation({
    mutationFn: (domainId: string) => pagesApi.deleteDomain(domainId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-domains', selectedPageId] })
      toast.success('Domain removed')
    },
  })

  const createSplitTestMutation = useMutation({
    mutationFn: ({ pageId, name }: { pageId: string; name: string }) =>
      pagesApi.createSplitTest(pageId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      setShowCreateTest(false)
      setNewTestName('')
      toast.success('Split test created')
    },
    onError: () => toast.error('Failed to create split test'),
  })

  const duplicateVariationMutation = useMutation({
    mutationFn: ({ testId, pageId }: { testId: string; pageId: string }) =>
      pagesApi.duplicateVariation(testId, pageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      toast.success('Variation created')
    },
  })

  const startTestMutation = useMutation({
    mutationFn: (testId: string) => pagesApi.startTest(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      toast.success('Test started')
    },
  })

  const pauseTestMutation = useMutation({
    mutationFn: (testId: string) => pagesApi.pauseTest(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      toast.success('Test paused')
    },
  })

  const stopTestMutation = useMutation({
    mutationFn: (testId: string) => pagesApi.stopTest(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      toast.success('Test stopped')
    },
  })

  const declareWinnerMutation = useMutation({
    mutationFn: ({ testId, variationId }: { testId: string; variationId: string }) =>
      pagesApi.declareWinner(testId, variationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['split-tests', selectedPageId] })
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      toast.success('Winner declared!')
    },
  })

  // -------------------------------------------------------------------------
  // Auto-save (debounced 10s draft save)
  // -------------------------------------------------------------------------

  const triggerAutoSave = useCallback(() => {
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    autoSaveTimerRef.current = setTimeout(() => {
      if (selectedPageId) {
        updateMutation.mutate({
          id: selectedPageId,
          data: { html_content: htmlRef.current, css_content: cssRef.current },
        })
      }
    }, 10000)
  }, [selectedPageId])

  const handleHtmlChange = useCallback(
    (val: string) => {
      setEditHtml(val)
      triggerAutoSave()
    },
    [triggerAutoSave],
  )

  const handleCssChange = useCallback(
    (val: string) => {
      setEditCss(val)
      triggerAutoSave()
    },
    [triggerAutoSave],
  )

  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    }
  }, [selectedPageId])

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleSave = () => {
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    if (selectedPageId) {
      updateMutation.mutate({
        id: selectedPageId,
        data: { html_content: editHtml, css_content: editCss },
      })
    }
  }

  const handlePublish = () => {
    if (selectedPageId) publishMutation.mutate(selectedPageId)
  }

  const handleUpdateLive = () => {
    if (selectedPageId) {
      // Save draft first, then push to live
      handleSave()
      setTimeout(() => updateLiveMutation.mutate(selectedPageId), 500)
    }
  }

  const handleDiscardChanges = () => {
    if (detail?.live_html_content) {
      setEditHtml(detail.live_html_content)
      setEditCss(detail.live_css_content || '')
      if (selectedPageId) {
        updateMutation.mutate({
          id: selectedPageId,
          data: { html_content: detail.live_html_content, css_content: detail.live_css_content || '' },
        })
      }
      setHasUnpublishedChanges(false)
      toast.success('Changes discarded')
    }
  }

  const handleSendChat = () => {
    const msg = chatInput.trim()
    if (!msg || !selectedPageId) return
    setChatMessages((prev) => [...prev, { role: 'user', content: msg }])
    setChatInput('')
    aiChatMutation.mutate({ page_id: selectedPageId, message: msg })
  }

  const handleChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendChat()
    }
  }

  const goBack = () => {
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    setView('list')
    setSelectedPageId(null)
    setSelectedWebsiteId(null)
    setActiveTab('preview')
    setChatMessages([])
    setEditHtml('')
    setEditCss('')
    setDraftSaved(false)
    setHasUnpublishedChanges(false)
  }

  const openPage = (page: PageItem) => {
    setSelectedPageId(page.id)
    setActiveTab('preview')
    if (page.website_id) {
      setSelectedWebsiteId(page.website_id)
      setView('website-edit')
    } else {
      setSelectedWebsiteId(null)
      setView('edit')
    }
  }

  const openWebsite = (ws: WebsiteItem) => {
    setSelectedWebsiteId(ws.id)
    setSelectedPageId(null)
    setView('website-edit')
  }

  // -------------------------------------------------------------------------
  // Shared: Preview iframe srcdoc
  // -------------------------------------------------------------------------

  const isFullDocument = editHtml.trim().toLowerCase().startsWith('<!doctype') || editHtml.trim().toLowerCase().startsWith('<html')
  const previewSrcDoc = isFullDocument
    ? (editCss.trim()
        ? editHtml.replace('</head>', `<style>${editCss}</style></head>`)
        : editHtml)
    : `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"><\/script><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"><script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"><\/script><style>body{font-family:'Inter',system-ui,sans-serif;margin:0}${editCss}</style></head><body>${editHtml}<script>lucide.createIcons();<\/script></body></html>`

  // -------------------------------------------------------------------------
  // Render: Create Page Modal
  // -------------------------------------------------------------------------

  const renderCreatePageModal = () => {
    if (!showCreatePage) return null
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Create New Page</h3>
            <button onClick={() => { setShowCreatePage(false); setCreatePageTitle('') }} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"><X className="h-5 w-5" /></button>
          </div>
          <input
            value={createPageTitle} onChange={(e) => setCreatePageTitle(e.target.value)}
            placeholder="Page title" autoFocus
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
            onKeyDown={(e) => { if (e.key === 'Enter' && createPageTitle.trim()) createPageMutation.mutate({ title: createPageTitle.trim() }) }}
          />
          <button
            onClick={() => createPageMutation.mutate({ title: createPageTitle.trim() })}
            disabled={!createPageTitle.trim() || createPageMutation.isPending}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {createPageMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {createPageMutation.isPending ? 'Creating...' : 'Create Page'}
          </button>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Create Website Modal
  // -------------------------------------------------------------------------

  const renderCreateWebsiteModal = () => {
    if (!showCreateWebsite) return null
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Create New Website</h3>
            <button onClick={() => { setShowCreateWebsite(false); setCreateWebsiteName('') }} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"><X className="h-5 w-5" /></button>
          </div>
          <input
            value={createWebsiteName} onChange={(e) => setCreateWebsiteName(e.target.value)}
            placeholder="Website name" autoFocus
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
            onKeyDown={(e) => { if (e.key === 'Enter' && createWebsiteName.trim()) createWebsiteMutation.mutate({ name: createWebsiteName.trim() }) }}
          />
          <button
            onClick={() => createWebsiteMutation.mutate({ name: createWebsiteName.trim() })}
            disabled={!createWebsiteName.trim() || createWebsiteMutation.isPending}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {createWebsiteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
            {createWebsiteMutation.isPending ? 'Creating...' : 'Create Website'}
          </button>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Save as Template Modal
  // -------------------------------------------------------------------------

  const renderSaveTemplateModal = () => {
    if (!showSaveTemplate) return null
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Save as Template</h3>
            <button onClick={() => setShowSaveTemplate(false)} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"><X className="h-5 w-5" /></button>
          </div>
          <div className="space-y-3">
            <input value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="Template name" autoFocus
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <textarea value={templateDesc} onChange={(e) => setTemplateDesc(e.target.value)} placeholder="Description (optional)" rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
            <div className="grid grid-cols-2 gap-3">
              <select value={templateIndustry} onChange={(e) => setTemplateIndustry(e.target.value)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Industry...</option>
                <option value="agency">Agency</option><option value="saas">SaaS</option><option value="restaurant">Restaurant</option>
                <option value="real-estate">Real Estate</option><option value="healthcare">Healthcare</option><option value="portfolio">Portfolio</option>
                <option value="ecommerce">E-Commerce</option><option value="events">Events</option><option value="professional">Professional Services</option>
              </select>
              <select value={templateType} onChange={(e) => setTemplateType(e.target.value)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Page type...</option>
                <option value="landing">Landing Page</option><option value="homepage">Homepage</option><option value="about">About</option>
                <option value="contact">Contact</option><option value="pricing">Pricing</option><option value="services">Services</option>
              </select>
            </div>
          </div>
          <button
            onClick={() => {
              if (!templateName.trim() || !selectedPageId) return
              saveTemplateMutation.mutate({ name: templateName.trim(), description: templateDesc.trim() || undefined, category_industry: templateIndustry || undefined, category_type: templateType || undefined, source_page_id: selectedPageId, scope: 'org' })
            }}
            disabled={!templateName.trim() || saveTemplateMutation.isPending}
            className="w-full mt-4 flex items-center justify-center gap-2 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {saveTemplateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bookmark className="h-4 w-4" />}
            {saveTemplateMutation.isPending ? 'Saving...' : 'Save Template'}
          </button>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Template preview
  // -------------------------------------------------------------------------

  const openTemplatePreview = async (templateId: string, name: string) => {
    setPreviewTemplateId(templateId)
    setPreviewTemplateName(name)
    setPreviewTemplateHtml('')
    setLoadingPreview(true)
    setPreviewDevice('desktop')
    try {
      const res = await pagesApi.getTemplate(templateId)
      const html = (res as any)?.data?.html_content || ''
      setPreviewTemplateHtml(html)
    } catch {
      toast.error('Failed to load template preview')
      setPreviewTemplateId(null)
    } finally {
      setLoadingPreview(false)
    }
  }

  const renderTemplatePreview = () => {
    if (!previewTemplateId) return null
    const deviceWidths = { desktop: '100%', tablet: '768px', mobile: '375px' }
    const previewWidth = deviceWidths[previewDevice]
    const previewSrc = (() => {
      if (!previewTemplateHtml) return ''
      const trimmed = previewTemplateHtml.trim().toLowerCase()
      if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')) return previewTemplateHtml
      return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"><\/script><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"><script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"><\/script></head><body>${previewTemplateHtml}<script>lucide.createIcons();<\/script></body></html>`
    })()

    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-[95vw] h-[92vh] flex flex-col">
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <div className="flex items-center gap-3">
              <button onClick={() => setPreviewTemplateId(null)} className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><ArrowLeft className="h-4 w-4" /></button>
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{previewTemplateName}</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">Template Preview</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
                {([['desktop', Monitor], ['tablet', Tablet], ['mobile', Smartphone]] as const).map(([device, Icon]) => (
                  <button key={device} onClick={() => setPreviewDevice(device)}
                    className={`p-1.5 rounded-md transition ${previewDevice === device ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`} title={device}>
                    <Icon className="h-4 w-4" />
                  </button>
                ))}
              </div>
              <button onClick={() => { const tId = previewTemplateId; setPreviewTemplateId(null); const title = prompt('Page title:'); if (title?.trim()) createFromTemplateMutation.mutate({ templateId: tId, title: title.trim(), websiteId: selectedWebsiteId || undefined }) }}
                disabled={createFromTemplateMutation.isPending}
                className="flex items-center gap-1.5 bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition">
                <Plus className="h-3.5 w-3.5" /> Use This Template
              </button>
              <button onClick={() => setPreviewTemplateId(null)} className="p-1.5 text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
            </div>
          </div>
          <div className="flex-1 overflow-auto bg-gray-200 dark:bg-gray-950 flex justify-center p-4">
            {loadingPreview ? (
              <div className="flex items-center justify-center h-full"><Loader2 className="h-8 w-8 text-blue-500 animate-spin" /></div>
            ) : (
              <div style={{ width: previewWidth, maxWidth: '100%', transition: 'width 0.3s ease' }} className="h-full bg-white rounded-lg shadow-lg overflow-hidden">
                <iframe srcDoc={previewSrc} className="w-full h-full border-0" sandbox="allow-scripts allow-same-origin allow-popups" title="Template preview" />
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Template Browser Modal
  // -------------------------------------------------------------------------

  const INDUSTRY_LABELS: Record<string, string> = {
    agency: 'Agency', saas: 'SaaS', restaurant: 'Restaurant & Food', 'real-estate': 'Real Estate',
    healthcare: 'Healthcare & Dental', portfolio: 'Portfolio & Creative', ecommerce: 'E-Commerce',
    events: 'Events & Venues', professional: 'Professional Services', fitness: 'Fitness & Wellness',
    education: 'Education', consulting: 'Consulting', legal: 'Legal', automotive: 'Automotive',
    beauty: 'Beauty & Spa', technology: 'Technology', nonprofit: 'Non-Profit',
  }
  const INDUSTRY_ORDER = ['agency', 'saas', 'restaurant', 'real-estate', 'healthcare', 'portfolio', 'ecommerce', 'events', 'professional', 'fitness', 'education', 'consulting', 'legal', 'automotive', 'beauty', 'technology', 'nonprofit']

  const renderTemplateCard = (t: TemplateItem) => (
    <div key={t.id} className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden hover:shadow-md transition group">
      <div className="h-32 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-700 dark:to-gray-800 flex items-center justify-center relative cursor-pointer"
        onClick={() => openTemplatePreview(t.id, t.name)}>
        <LayoutTemplate className="h-8 w-8 text-gray-300 dark:text-gray-600" />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition flex items-center justify-center opacity-0 group-hover:opacity-100">
          <Eye className="h-6 w-6 text-white drop-shadow-lg" />
        </div>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between">
          <h4 className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">{t.name}</h4>
          <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete template?')) deleteTemplateMutation.mutate(t.id) }}
            className="p-0.5 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition flex-shrink-0"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
        {t.description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{t.description}</p>}
        <div className="flex items-center gap-1.5 mt-2">
          {t.category_industry && <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full">{t.category_industry}</span>}
          {t.scope === 'platform' && <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-full">Starter</span>}
        </div>
        <button onClick={() => { const title = prompt('Page title:'); if (title?.trim()) createFromTemplateMutation.mutate({ templateId: t.id, title: title.trim(), websiteId: selectedWebsiteId || undefined }) }}
          disabled={createFromTemplateMutation.isPending}
          className="w-full mt-3 flex items-center justify-center gap-1 bg-blue-600 text-white py-1.5 rounded-lg text-xs hover:bg-blue-700 disabled:opacity-50 transition">
          <Plus className="h-3 w-3" /> Use Template
        </button>
      </div>
    </div>
  )

  const renderTemplateBrowser = () => {
    if (!showTemplateBrowser) return null
    const filtered = templates.filter((t) => {
      if (templateSearch && !t.name.toLowerCase().includes(templateSearch.toLowerCase()) && !t.description?.toLowerCase().includes(templateSearch.toLowerCase())) return false
      if (templateFilterIndustry && t.category_industry !== templateFilterIndustry) return false
      return true
    })
    const grouped: Record<string, TemplateItem[]> = {}
    for (const t of filtered) { const key = t.category_industry || 'other'; if (!grouped[key]) grouped[key] = []; grouped[key].push(t) }
    const sortedGroups = INDUSTRY_ORDER.filter((k) => grouped[k]?.length).map((k) => [k, grouped[k]] as const)
    for (const k of Object.keys(grouped)) { if (!INDUSTRY_ORDER.includes(k)) sortedGroups.push([k, grouped[k]] as const) }
    const availableIndustries = [...new Set(templates.map((t) => t.category_industry).filter(Boolean))]

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Template Library</h3>
              <p className="text-xs text-gray-500 mt-0.5">{templates.length} premium templates</p>
            </div>
            <button onClick={() => { setShowTemplateBrowser(false); setTemplateSearch(''); setTemplateFilterIndustry('') }} className="p-1 text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
          </div>
          <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-200 dark:border-gray-700">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input value={templateSearch} onChange={(e) => setTemplateSearch(e.target.value)} placeholder="Search templates..."
                className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" />
            </div>
            <div className="flex gap-1 flex-wrap">
              <button onClick={() => setTemplateFilterIndustry('')}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition ${!templateFilterIndustry ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200'}`}>All</button>
              {availableIndustries.sort().map((ind) => (
                <button key={ind} onClick={() => setTemplateFilterIndustry(ind === templateFilterIndustry ? '' : ind!)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition ${templateFilterIndustry === ind ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200'}`}>{INDUSTRY_LABELS[ind!] || ind}</button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-6 space-y-8">
            {filtered.length === 0 ? (
              <div className="text-center py-12 text-gray-400"><LayoutTemplate className="h-10 w-10 mx-auto mb-3 opacity-40" /><p className="text-sm">No templates found</p></div>
            ) : templateFilterIndustry ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{filtered.map((t) => renderTemplateCard(t))}</div>
            ) : (
              sortedGroups.map(([industry, items]) => (
                <div key={industry}>
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">{INDUSTRY_LABELS[industry] || industry} <span className="text-xs font-normal text-gray-400">({items.length})</span></h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{items.map((t) => renderTemplateCard(t))}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    )
  }

  // =========================================================================
  // LIST VIEW
  // =========================================================================

  if (view === 'list') {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        {renderCreatePageModal()}
        {renderCreateWebsiteModal()}
        {renderTemplateBrowser()}
        {renderTemplatePreview()}

        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Page Builder</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Build websites and landing pages with AI</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowTemplateBrowser(true)} className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
              <LayoutTemplate className="h-4 w-4" /> From Template
            </button>
            <button onClick={() => setShowCreateWebsite(true)} className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
              <Globe className="h-4 w-4" /> New Website
            </button>
            <button onClick={() => setShowCreatePage(true)} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition">
              <Plus className="h-4 w-4" /> New Page
            </button>
          </div>
        </div>

        {/* Websites */}
        <div className="mb-10">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2"><Globe className="h-5 w-5 text-blue-500" /> Websites</h2>
          {websitesLoading ? (
            <div className="flex items-center gap-2 text-gray-400 py-8"><Loader2 className="h-5 w-5 animate-spin" /> Loading...</div>
          ) : websites.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-dashed border-gray-300 dark:border-gray-700">
              <Globe className="h-10 w-10 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
              <p className="text-gray-500 dark:text-gray-400">No websites yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {websites.map((ws) => (
                <div key={ws.id} onClick={() => openWebsite(ws)} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 hover:shadow-md transition cursor-pointer group">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2"><Globe className="h-5 w-5 text-blue-500" /><h3 className="font-semibold text-gray-900 dark:text-gray-100">{ws.name}</h3></div>
                    <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete this website?')) deleteWebsiteMutation.mutate(ws.id) }} className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition"><Trash2 className="h-4 w-4" /></button>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">{ws.page_count} {ws.page_count === 1 ? 'page' : 'pages'}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ws.is_published ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>{ws.is_published ? 'Published' : 'Draft'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Standalone Pages */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2"><FileText className="h-5 w-5 text-purple-500" /> Standalone Pages</h2>
          {pagesLoading ? (
            <div className="flex items-center gap-2 text-gray-400 py-8"><Loader2 className="h-5 w-5 animate-spin" /> Loading...</div>
          ) : standalonePages.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-dashed border-gray-300 dark:border-gray-700">
              <FileText className="h-10 w-10 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
              <p className="text-gray-500 dark:text-gray-400">No standalone pages yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {standalonePages.map((p) => (
                <div key={p.id} onClick={() => openPage(p)} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 hover:shadow-md transition cursor-pointer group">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100">{p.title}</h3>
                    <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete this page?')) deletePageMutation.mutate(p.id) }} className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition"><Trash2 className="h-4 w-4" /></button>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">/{p.slug}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${p.status === 'published' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>{p.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // =========================================================================
  // EDIT VIEW & WEBSITE-EDIT VIEW
  // =========================================================================

  const isWebsiteEdit = view === 'website-edit'

  // -------------------------------------------------------------------------
  // Render: Pages Sidebar (website-edit only)
  // -------------------------------------------------------------------------

  const renderPagesSidebar = () => {
    if (!isWebsiteEdit) return null
    return (
      <div className="w-[200px] flex-shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex flex-col overflow-hidden">
        <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Pages</span>
          <button onClick={() => { if (!selectedWebsiteId) return; const title = prompt('New page title:'); if (title?.trim()) createPageMutation.mutate({ title: title.trim(), website_id: selectedWebsiteId }) }}
            className="p-1 text-gray-400 hover:text-blue-500 transition" title="Add page"><Plus className="h-4 w-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {websitePages.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-4">No pages yet</p>
          ) : websitePages.map((wp) => (
            <button key={wp.id} onClick={() => setSelectedPageId(wp.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition truncate ${wp.id === selectedPageId ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
              <div className="flex items-center gap-2"><FileText className="h-3.5 w-3.5 flex-shrink-0" /><span className="truncate">{wp.title}</span></div>
              {wp.is_homepage && <span className="text-[10px] text-blue-500 ml-5">Home</span>}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Chat Panel (O-Brain) — 25% width
  // -------------------------------------------------------------------------

  const renderChatPanel = () => (
    <div className="flex flex-col overflow-hidden bg-white dark:bg-gray-900 h-full">
      {/* Header with purple sparkle */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
        <div className="relative">
          <Brain className="h-4 w-4 text-purple-500" />
          <Sparkles className="h-2.5 w-2.5 text-purple-400 absolute -top-1 -right-1" />
        </div>
        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">O-Brain</span>
        {aiChatMutation.isPending && (
          <span className="ml-auto flex items-center gap-1 text-xs text-purple-500">
            <Loader2 className="h-3 w-3 animate-spin" /> Generating...
          </span>
        )}
        <button onClick={() => setChatCollapsed(true)} className="ml-auto p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition" title="Collapse chat">
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {/* Messages — overflow contained */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4" style={{ overflowWrap: 'break-word' }}>
        {chatMessages.length === 0 && !aiChatMutation.isPending && (
          <div className="text-center py-12 text-gray-400 dark:text-gray-500">
            <Brain className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">Tell O-Brain what you want to build.</p>
            <p className="text-xs mt-1">Your page will appear in the preview panel.</p>
          </div>
        )}
        {chatMessages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap break-words ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-md' : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md'}`}
              style={{ overflowWrap: 'break-word', wordBreak: 'break-word', maxWidth: '100%' }}>
              {msg.content}
            </div>
          </div>
        ))}
        {aiChatMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm text-gray-500 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Generating...
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex gap-2">
          <textarea value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={handleChatKeyDown}
            placeholder="Tell O-Brain what you want..." rows={2}
            className="flex-1 min-w-0 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-purple-500" />
          <button onClick={handleSendChat} disabled={!chatInput.trim() || aiChatMutation.isPending || !selectedPageId}
            className="self-end flex-shrink-0 p-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition">
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )

  // -------------------------------------------------------------------------
  // Render: Settings Tab Content
  // -------------------------------------------------------------------------

  const renderSettingsContent = () => {
    if (!selectedPageId) return null

    return (
      <div className="h-full overflow-y-auto p-6 space-y-8">
        {/* Auto-publish toggle */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Publishing</h3>
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={detail?.auto_publish || false}
              onChange={(e) => updateMutation.mutate({ id: selectedPageId, data: { auto_publish: e.target.checked } })}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            <div>
              <p className="text-sm text-gray-900 dark:text-gray-100">Auto-publish changes</p>
              <p className="text-xs text-gray-500">Changes will go live immediately. Recommended only for low-traffic sites.</p>
            </div>
          </label>
        </div>

        {/* Version History */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
            <History className="h-4 w-4" /> Version History
          </h3>
          {versions.length === 0 ? (
            <p className="text-sm text-gray-400">No versions yet.</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {versions.slice(0, 50).map((v) => (
                <div key={v.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">v{v.version_number}</p>
                    <p className="text-xs text-gray-500">{v.change_summary || 'No summary'}</p>
                    <p className="text-[10px] text-gray-400">{new Date(v.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    {v.html_content && (
                      <button onClick={() => { setCompareVersionId(v.id); setCompareHtml(v.html_content || '') }}
                        className="p-1 text-gray-400 hover:text-blue-500 transition" title="Compare">
                        <Columns2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button onClick={() => { if (confirm(`Restore to v${v.version_number}?`)) restoreVersionMutation.mutate({ pageId: selectedPageId, versionId: v.id }) }}
                      className="p-1 text-gray-400 hover:text-green-500 transition" title="Restore">
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Custom Domains */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
            <Link className="h-4 w-4" /> Custom Domain
          </h3>
          {domains.map((d) => (
            <div key={d.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded-lg mb-2">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{d.domain}</p>
                <div className="flex items-center gap-2 mt-1">
                  {d.dns_verified ? (
                    <span className="flex items-center gap-1 text-xs text-green-600"><Shield className="h-3 w-3" /> Connected {d.ssl_status === 'active' ? '(SSL Active)' : ''}</span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-amber-600"><Clock className="h-3 w-3" /> Pending DNS</span>
                  )}
                </div>
                {!d.dns_verified && d.dns_target && (
                  <div className="mt-2 p-2 bg-gray-100 dark:bg-gray-900 rounded text-xs">
                    <p className="font-medium text-gray-700 dark:text-gray-300">Add this {d.dns_record_type} record:</p>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="text-purple-600 dark:text-purple-400">{d.dns_target}</code>
                      <button onClick={() => { navigator.clipboard.writeText(d.dns_target || ''); toast.success('Copied!') }} className="p-0.5 text-gray-400 hover:text-blue-500"><Copy className="h-3 w-3" /></button>
                    </div>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1">
                {!d.dns_verified && (
                  <button onClick={() => verifyDomainMutation.mutate(d.id)} disabled={verifyDomainMutation.isPending}
                    className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">Verify</button>
                )}
                <button onClick={() => { if (confirm('Remove this domain?')) deleteDomainMutation.mutate(d.id) }}
                  className="p-1 text-gray-400 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          ))}
          <div className="flex gap-2 mt-2">
            <input value={newDomain} onChange={(e) => setNewDomain(e.target.value)} placeholder="www.yourdomain.com"
              className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => { if (e.key === 'Enter' && newDomain.trim()) addDomainMutation.mutate({ pageId: selectedPageId, domain: newDomain.trim() }) }} />
            <button onClick={() => { if (newDomain.trim()) addDomainMutation.mutate({ pageId: selectedPageId, domain: newDomain.trim() }) }}
              disabled={!newDomain.trim() || addDomainMutation.isPending}
              className="px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition">Add</button>
          </div>
        </div>

        {/* Split Testing */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
            <FlaskConical className="h-4 w-4" /> Split Testing
          </h3>
          {splitTests.map((test) => (
            <div key={test.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg mb-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100">{test.name}</h4>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    test.status === 'running' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                    test.status === 'paused' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                    test.status === 'completed' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                    'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                  }`}>{test.status}</span>
                </div>
                <div className="flex items-center gap-1">
                  {test.status === 'draft' && (
                    <>
                      <button onClick={() => duplicateVariationMutation.mutate({ testId: test.id, pageId: selectedPageId })}
                        className="text-[10px] px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded hover:bg-gray-300 transition">+ Variation</button>
                      <button onClick={() => startTestMutation.mutate(test.id)} className="p-1 text-green-500 hover:text-green-600"><Play className="h-3.5 w-3.5" /></button>
                    </>
                  )}
                  {test.status === 'running' && (
                    <button onClick={() => pauseTestMutation.mutate(test.id)} className="p-1 text-amber-500 hover:text-amber-600"><Pause className="h-3.5 w-3.5" /></button>
                  )}
                  {test.status === 'paused' && (
                    <>
                      <button onClick={() => startTestMutation.mutate(test.id)} className="p-1 text-green-500 hover:text-green-600"><Play className="h-3.5 w-3.5" /></button>
                      <button onClick={() => stopTestMutation.mutate(test.id)} className="p-1 text-red-500 hover:text-red-600"><Square className="h-3.5 w-3.5" /></button>
                    </>
                  )}
                </div>
              </div>
              {/* Variations table */}
              {test.variations.length > 0 && (
                <div className="text-xs">
                  <div className="grid grid-cols-5 gap-2 text-gray-500 mb-1 font-medium">
                    <span>Variation</span><span>Traffic</span><span>Visitors</span><span>Conv.</span><span>Rate</span>
                  </div>
                  {test.variations.map((v) => {
                    const rate = v.visitors > 0 ? ((v.conversions / v.visitors) * 100).toFixed(1) : '0.0'
                    return (
                      <div key={v.id} className="grid grid-cols-5 gap-2 py-1 text-gray-900 dark:text-gray-100">
                        <span className="truncate">{v.name}</span>
                        <span>{v.traffic_percentage}%</span>
                        <span>{v.visitors}</span>
                        <span>{v.conversions}</span>
                        <div className="flex items-center gap-1">
                          <span>{rate}%</span>
                          {(test.status === 'running' || test.status === 'completed') && !test.winner_variation_id && (
                            <button onClick={() => declareWinnerMutation.mutate({ testId: test.id, variationId: v.id })}
                              className="p-0.5 text-amber-500 hover:text-amber-600" title="Declare winner"><Trophy className="h-3 w-3" /></button>
                          )}
                          {test.winner_variation_id === v.id && <Trophy className="h-3 w-3 text-amber-500" />}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
          <button onClick={() => setShowCreateTest(true)}
            className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-700 font-medium">
            <Plus className="h-3.5 w-3.5" /> New Split Test
          </button>
          {showCreateTest && (
            <div className="mt-2 flex gap-2">
              <input value={newTestName} onChange={(e) => setNewTestName(e.target.value)} placeholder="Test name"
                className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                onKeyDown={(e) => { if (e.key === 'Enter' && newTestName.trim()) createSplitTestMutation.mutate({ pageId: selectedPageId, name: newTestName.trim() }) }} />
              <button onClick={() => { if (newTestName.trim()) createSplitTestMutation.mutate({ pageId: selectedPageId, name: newTestName.trim() }) }}
                disabled={!newTestName.trim()} className="px-3 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50">Create</button>
              <button onClick={() => { setShowCreateTest(false); setNewTestName('') }} className="p-2 text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
            </div>
          )}
        </div>

        {/* Tracking Pixels */}
        <TrackingPixelsSettings
          value={detail?.tracking_pixels_json || '{}'}
          onChange={(json: string) => { if (selectedPageId) updateMutation.mutate({ id: selectedPageId, data: { tracking_pixels_json: json } }) }}
        />
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Version Compare Modal
  // -------------------------------------------------------------------------

  const renderCompareModal = () => {
    if (!compareVersionId) return null
    const compareSrc = (() => {
      if (!compareHtml) return ''
      const trimmed = compareHtml.trim().toLowerCase()
      if (trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')) return compareHtml
      return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdn.tailwindcss.com"><\/script></head><body>${compareHtml}</body></html>`
    })()

    return (
      <div className="fixed inset-0 z-[60] flex bg-black/70 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full flex flex-col">
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Compare: Current vs Selected Version</h3>
            <button onClick={() => setCompareVersionId(null)} className="p-1.5 text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
          </div>
          <div className="flex-1 flex gap-4 p-4 overflow-hidden">
            <div className="flex-1 flex flex-col">
              <p className="text-xs font-medium text-gray-500 mb-2">Current Draft</p>
              <iframe srcDoc={previewSrcDoc} className="flex-1 w-full border border-gray-200 dark:border-gray-700 rounded-lg" sandbox="allow-scripts allow-same-origin" title="Current" />
            </div>
            <div className="flex-1 flex flex-col">
              <p className="text-xs font-medium text-gray-500 mb-2">Selected Version</p>
              <iframe srcDoc={compareSrc} className="flex-1 w-full border border-gray-200 dark:border-gray-700 rounded-lg" sandbox="allow-scripts allow-same-origin" title="Version" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Render: Editor Tabs (right panel — 75%)
  // -------------------------------------------------------------------------

  const renderEditorPanel = () => (
    <div className="h-full flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950" style={{ height: 'calc(100vh - 48px)' }}>
      {/* Tabs */}
      <div className="flex items-center border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 shrink-0">
        {(
          [
            { key: 'preview', label: 'Preview', icon: Eye },
            { key: 'visual', label: 'Visual', icon: Paintbrush },
            { key: 'html', label: 'HTML', icon: Code },
            { key: 'css', label: 'CSS', icon: Code },
            { key: 'analytics', label: 'Analytics', icon: BarChart3 },
            { key: 'settings', label: 'Settings', icon: Settings },
          ] as { key: EditorTab; label: string; icon: typeof Eye }[]
        ).map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition ${activeTab === key ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700'}`}>
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}

        {activeTab === 'preview' && (
          <div className="ml-auto flex items-center gap-1 pr-2">
            {([{ key: 'desktop', icon: Monitor }, { key: 'tablet', icon: Tablet }, { key: 'mobile', icon: Smartphone }] as { key: ResponsiveSize; icon: typeof Monitor }[]).map(({ key, icon: Icon }) => (
              <button key={key} onClick={() => setResponsiveSize(key)}
                className={`p-1.5 rounded transition ${responsiveSize === key ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`} title={key}>
                <Icon className="h-4 w-4" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tab content — fills to bottom */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'preview' && (
          <div className="h-full flex justify-center bg-gray-100 dark:bg-gray-950 overflow-hidden">
            <div className="bg-white shadow-lg transition-all duration-300 flex-shrink-0"
              style={{ width: RESPONSIVE_WIDTHS[responsiveSize], maxWidth: '100%', height: '100%' }}>
              {pageDetailLoading ? (
                <div className="flex items-center justify-center h-full text-gray-400"><Loader2 className="h-6 w-6 animate-spin" /></div>
              ) : (
                <iframe srcDoc={previewSrcDoc} className="w-full h-full border-0" title="Page preview"
                  sandbox="allow-scripts allow-same-origin allow-popups" style={{ display: 'block' }} />
              )}
            </div>
          </div>
        )}

        {activeTab === 'visual' && (
          <VisualEditor html={editHtml} css={editCss} onHtmlChange={handleHtmlChange} onCssChange={handleCssChange}
            onVideoUpload={async (file: File) => { const res = await pagesApi.uploadVideo(file); return unwrap<{ mp4_url: string; webm_url: string; poster_url: string }>(res) }} />
        )}

        {activeTab === 'html' && (
          <div className="h-full flex flex-col overflow-hidden">
            <div className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-xs font-medium text-gray-500 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
              <span>HTML</span><span className="text-[10px] text-gray-400">{editHtml.length} characters</span>
            </div>
            <textarea value={editHtml} onChange={(e) => handleHtmlChange(e.target.value)}
              className="flex-1 w-full p-4 font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 resize-none focus:outline-none leading-relaxed"
              spellCheck={false} placeholder="<div>Your HTML content here...</div>" />
          </div>
        )}

        {activeTab === 'css' && (
          <div className="h-full flex flex-col overflow-hidden">
            <div className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-xs font-medium text-gray-500 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
              <span>CSS</span><span className="text-[10px] text-gray-400">{editCss.length} characters</span>
            </div>
            <textarea value={editCss} onChange={(e) => handleCssChange(e.target.value)}
              className="flex-1 w-full p-4 font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 resize-none focus:outline-none leading-relaxed"
              spellCheck={false} placeholder="body { font-family: sans-serif; }" />
          </div>
        )}

        {activeTab === 'analytics' && selectedPageId && (
          <AnalyticsDashboard pageId={selectedPageId} onClose={() => setActiveTab('preview')} />
        )}

        {activeTab === 'settings' && selectedPageId && renderSettingsContent()}
      </div>
    </div>
  )

  // -------------------------------------------------------------------------
  // Render: Top Bar
  // -------------------------------------------------------------------------

  const renderTopBar = () => (
    <div className="h-12 flex-shrink-0 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 flex items-center justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={goBack} className="p-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h2 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
          {pageDetailLoading ? 'Loading...' : detail?.title || 'Select a page'}
        </h2>
        {detail && (
          <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${detail.status === 'published' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>
            {detail.status}
          </span>
        )}
        {/* Draft saved indicator */}
        {draftSaved && (
          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
            <Check className="h-3 w-3" /> Draft saved
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button onClick={() => setShowSaveTemplate(true)} disabled={!selectedPageId}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition" title="Save as Template">
          <Bookmark className="h-4 w-4" /> Template
        </button>

        {/* Save button */}
        <button onClick={handleSave} disabled={updateMutation.isPending || !selectedPageId}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-800 dark:bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 transition">
          {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
        </button>

        {/* Publish button (draft pages only) */}
        {detail && !isPublished && (
          <button onClick={handlePublish} disabled={publishMutation.isPending || !selectedPageId}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition">
            {publishMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Publish
          </button>
        )}

        {/* Update button (published pages with changes) */}
        {isPublished && (
          <>
            <button onClick={handleUpdateLive}
              disabled={updateLiveMutation.isPending || !selectedPageId}
              className="relative flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition">
              {updateLiveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Update
              {hasUnpublishedChanges && (
                <span className="absolute -top-1 -right-1 h-2.5 w-2.5 bg-red-500 rounded-full border-2 border-white dark:border-gray-800" />
              )}
            </button>
            {hasUnpublishedChanges && (
              <button onClick={handleDiscardChanges}
                className="text-xs text-gray-500 hover:text-red-500 transition px-2 py-1">
                Discard
              </button>
            )}
          </>
        )}

        {/* View Live link */}
        {isPublished && (
          <a href={`/api/pages/public/view/${detail?.slug}`} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition">
            <ExternalLink className="h-4 w-4" /> View Live
          </a>
        )}
      </div>
    </div>
  )

  // =========================================================================
  // Compose editor layout
  // =========================================================================

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {renderCreatePageModal()}
      {renderCreateWebsiteModal()}
      {renderSaveTemplateModal()}
      {renderTemplateBrowser()}
      {renderTemplatePreview()}
      {renderCompareModal()}

      {renderTopBar()}

      <div className="flex-1 flex overflow-hidden">
        {renderPagesSidebar()}

        {isWebsiteEdit && !selectedPageId ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-40" />
              {websitePages.length > 0 ? (
                <p className="text-sm">Select a page from the sidebar.</p>
              ) : (
                <>
                  <p className="text-sm">No pages yet.</p>
                  <button onClick={() => { const title = prompt('New page title:'); if (title?.trim() && selectedWebsiteId) createPageMutation.mutate({ title: title.trim(), website_id: selectedWebsiteId }) }}
                    className="mt-3 flex items-center gap-2 mx-auto px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm transition">
                    <Plus className="h-4 w-4" /> Create First Page
                  </button>
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Chat panel — 25% width / 320px, collapsible */}
            {chatCollapsed ? (
              <div className="flex-shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col items-center py-3 px-1 bg-white dark:bg-gray-900 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                onClick={() => setChatCollapsed(false)}>
                <button className="p-1.5 text-gray-400 hover:text-purple-500 transition rounded-lg" title="Expand O-Brain">
                  <PanelLeftOpen className="h-4 w-4" />
                </button>
                <div className="mt-2 text-xs text-gray-400 font-medium" style={{ writingMode: 'vertical-rl' }}>O-Brain</div>
              </div>
            ) : (
              <div className="w-[25%] min-w-[280px] max-w-[360px] flex-shrink-0 border-r border-gray-200 dark:border-gray-700 overflow-hidden">
                {renderChatPanel()}
              </div>
            )}

            {/* Editor panel — fills remaining space (75%+) */}
            <div className="flex-1 overflow-hidden">
              {renderEditorPanel()}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
