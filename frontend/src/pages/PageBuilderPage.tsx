import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pagesApi } from '@/api/pages'
import type { PageItem, PageDetail, StylePreset } from '@/types/models'
import {
  Globe,
  Plus,
  Trash2,
  Eye,
  BarChart3,
  Sparkles,
  Send,
  ArrowLeft,
  History,
  RotateCcw,
  ExternalLink,
} from 'lucide-react'

type View = 'list' | 'create' | 'edit' | 'preview'

export default function PageBuilderPage() {
  const queryClient = useQueryClient()
  const [view, setView] = useState<View>('list')
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null)
  const [createTitle, setCreateTitle] = useState('')
  const [createPreset, setCreatePreset] = useState('modern')
  const [aiPrompt, setAiPrompt] = useState('')
  const [editHtml, setEditHtml] = useState('')
  const [editCss, setEditCss] = useState('')
  const [showVersions, setShowVersions] = useState(false)

  const { data: pagesData } = useQuery({
    queryKey: ['pages'],
    queryFn: () => pagesApi.list() as Promise<{ data: PageItem[]; meta: { total_count: number } }>,
  })

  const { data: presetsData } = useQuery({
    queryKey: ['style-presets'],
    queryFn: () => pagesApi.getStylePresets() as Promise<{ data: StylePreset[] }>,
  })

  const { data: pageDetail } = useQuery({
    queryKey: ['page', selectedPageId],
    queryFn: () => pagesApi.get(selectedPageId!) as Promise<{ data: PageDetail }>,
    enabled: !!selectedPageId,
  })

  const { data: versionsData } = useQuery({
    queryKey: ['page-versions', selectedPageId],
    queryFn: () => pagesApi.listVersions(selectedPageId!) as Promise<{ data: { id: string; version_number: number; change_summary?: string; created_at: string }[] }>,
    enabled: !!selectedPageId && showVersions,
  })

  const { data: analyticsData } = useQuery({
    queryKey: ['page-analytics', selectedPageId],
    queryFn: () => pagesApi.getAnalytics(selectedPageId!) as Promise<{ data: { total_views: number; unique_visitors: number; total_submissions: number; conversion_rate: number } }>,
    enabled: !!selectedPageId && view === 'edit',
  })

  const createMutation = useMutation({
    mutationFn: (data: { title: string; style_preset?: string }) => pagesApi.create(data) as Promise<{ data: PageDetail }>,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      setSelectedPageId(res.data.id)
      setView('edit')
      toast.success('Page created')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => pagesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      toast.success('Page saved')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => pagesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      setView('list')
      setSelectedPageId(null)
      toast.success('Page deleted')
    },
  })

  const publishMutation = useMutation({
    mutationFn: (id: string) => pagesApi.publish(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      toast.success('Page published!')
    },
  })

  const aiGenerateMutation = useMutation({
    mutationFn: (data: { prompt: string; style_preset?: string }) =>
      pagesApi.aiGenerate(data) as Promise<{ data: { html_content: string; css_content: string; js_content: string } }>,
    onSuccess: (res) => {
      setEditHtml(res.data.html_content || '')
      setEditCss(res.data.css_content || '')
      toast.success('AI content generated')
    },
  })

  const restoreVersionMutation = useMutation({
    mutationFn: ({ pageId, versionId }: { pageId: string; versionId: string }) =>
      pagesApi.restoreVersion(pageId, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page', selectedPageId] })
      toast.success('Version restored')
    },
  })

  const pages = pagesData?.data || []
  const presets = presetsData?.data || []
  const detail = pageDetail?.data
  const analytics = analyticsData?.data

  const openEditor = (pageId: string) => {
    setSelectedPageId(pageId)
    setView('edit')
  }

  // --- List View ---
  if (view === 'list') {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Page Builder</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Create AI-powered landing pages</p>
          </div>
          <button
            onClick={() => setView('create')}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            <Plus className="h-4 w-4" />
            New Page
          </button>
        </div>

        {pages.length === 0 ? (
          <div className="text-center py-20 text-gray-500 dark:text-gray-400">
            <Globe className="h-12 w-12 mx-auto mb-4 opacity-40" />
            <p>No pages yet. Create your first landing page.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {pages.map((p) => (
              <div
                key={p.id}
                className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition cursor-pointer"
                onClick={() => openEditor(p.id)}
              >
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">{p.title}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">/{p.slug}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                    p.status === 'published' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                  }`}>
                    {p.status}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(p.id) }}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // --- Create View ---
  if (view === 'create') {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <button onClick={() => setView('list')} className="flex items-center gap-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-6">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-6">Create New Page</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Page Title</label>
            <input
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              placeholder="My Landing Page"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Style Preset</label>
            <div className="grid grid-cols-3 gap-3">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => setCreatePreset(preset.id)}
                  className={`p-3 rounded-lg border text-left transition ${
                    createPreset === preset.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-4 h-4 rounded-full" style={{ background: preset.preview_colors.primary }} />
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{preset.name}</span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{preset.description}</p>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={() => createMutation.mutate({ title: createTitle, style_preset: createPreset })}
            disabled={!createTitle.trim() || createMutation.isPending}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Page'}
          </button>
        </div>
      </div>
    )
  }

  // --- Edit / Preview View ---
  return (
    <div className="h-full flex flex-col">
      {/* Top bar */}
      <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => { setView('list'); setSelectedPageId(null) }} className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">{detail?.title || 'Loading...'}</h2>
          {detail && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              detail.status === 'published' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
            }`}>
              {detail.status}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {analytics && (
            <div className="flex items-center gap-4 text-xs text-gray-500 mr-4">
              <span><BarChart3 className="h-3 w-3 inline mr-1" />{analytics.total_views} views</span>
              <span>{analytics.conversion_rate}% conversion</span>
            </div>
          )}
          <button
            onClick={() => setShowVersions(!showVersions)}
            className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            title="Version history"
          >
            <History className="h-4 w-4" />
          </button>
          <button
            onClick={() => setView(view === 'preview' ? 'edit' : 'preview')}
            className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
          >
            <Eye className="h-4 w-4" />
            {view === 'preview' ? 'Edit' : 'Preview'}
          </button>
          {detail?.status === 'published' && (
            <a
              href={`/api/pages/public/view/${detail.slug}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            >
              <ExternalLink className="h-4 w-4" />
              View Live
            </a>
          )}
          <button
            onClick={() => {
              if (selectedPageId) {
                updateMutation.mutate({ id: selectedPageId, data: { html_content: editHtml, css_content: editCss } })
              }
            }}
            disabled={updateMutation.isPending}
            className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded-lg hover:bg-gray-700 dark:bg-gray-600 dark:hover:bg-gray-500 disabled:opacity-50"
          >
            Save
          </button>
          {detail?.status !== 'published' && selectedPageId && (
            <button
              onClick={() => publishMutation.mutate(selectedPageId)}
              disabled={publishMutation.isPending}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              Publish
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Version history panel */}
        {showVersions && (
          <div className="w-64 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-3 overflow-y-auto">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Versions</h3>
            {(versionsData?.data || []).map((v) => (
              <div key={v.id} className="mb-2 p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">v{v.version_number}</span>
                  <button
                    onClick={() => selectedPageId && restoreVersionMutation.mutate({ pageId: selectedPageId, versionId: v.id })}
                    className="p-1 text-gray-400 hover:text-blue-500"
                    title="Restore"
                  >
                    <RotateCcw className="h-3 w-3" />
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">{v.change_summary || 'No description'}</p>
              </div>
            ))}
          </div>
        )}

        {/* Main editor area */}
        {view === 'preview' ? (
          <div className="flex-1 bg-white">
            <iframe
              srcDoc={`<!DOCTYPE html><html><head><style>${editCss || detail?.css_content || ''}</style></head><body>${editHtml || detail?.html_content || ''}</body></html>`}
              className="w-full h-full border-0"
              title="Page preview"
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* AI bar */}
            <div className="p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
              <div className="flex gap-2">
                <input
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  placeholder="Describe what you want AI to build or change..."
                />
                <button
                  onClick={() => {
                    if (selectedPageId && detail) {
                      aiGenerateMutation.mutate({ prompt: aiPrompt, style_preset: detail.style_preset || 'modern' })
                    }
                  }}
                  disabled={!aiPrompt.trim() || aiGenerateMutation.isPending}
                  className="flex items-center gap-1 px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                >
                  <Sparkles className="h-4 w-4" />
                  {aiGenerateMutation.isPending ? 'Generating...' : 'Generate'}
                </button>
              </div>
            </div>

            {/* Code editors */}
            <div className="flex-1 grid grid-cols-2 overflow-hidden">
              <div className="border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
                <div className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-xs font-medium text-gray-600 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">HTML</div>
                <textarea
                  value={editHtml || detail?.html_content || ''}
                  onChange={(e) => setEditHtml(e.target.value)}
                  className="flex-1 p-3 font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 resize-none focus:outline-none"
                  spellCheck={false}
                />
              </div>
              <div className="flex flex-col overflow-hidden">
                <div className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-xs font-medium text-gray-600 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">CSS</div>
                <textarea
                  value={editCss || detail?.css_content || ''}
                  onChange={(e) => setEditCss(e.target.value)}
                  className="flex-1 p-3 font-mono text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 resize-none focus:outline-none"
                  spellCheck={false}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
