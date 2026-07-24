import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getOfficeDoc, updateOfficeDoc, starOfficeDoc } from '@/api/office'
import { useAuthStore } from '@/stores/authStore'
import EditorTopBar from '@/components/office/EditorTopBar'
import DocToolbar from '@/components/office/DocToolbar'
import CommentsPanel from '@/components/office/CommentsPanel'
import VersionHistoryPanel from '@/components/office/VersionHistoryPanel'
import AiAssistPopover from '@/components/office/AiAssistPopover'
import {
  ChevronDown,
  ChevronRight,
  Download,
  Upload,
  Search,
  X,
  ZoomIn,
  ZoomOut,
  ListTree,
  PanelLeftClose,
  MessageSquare,
  History,
  Sparkles,
} from 'lucide-react'

import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'
import { TextStyle, Color, FontSize } from '@tiptap/extension-text-style'
import Collaboration from '@tiptap/extension-collaboration'
import type { JSONContent } from '@tiptap/react'
import * as Y from 'yjs'
import { HocuspocusProvider, WebSocketStatus } from '@hocuspocus/provider'

// ─── Collaboration cursor colors ───────────────────────────────────────────

const CURSOR_COLORS = ['#f87171', '#fb923c', '#fbbf24', '#a3e635', '#34d399', '#22d3ee', '#60a5fa', '#a78bfa', '#f472b6']

function colorForUser(userId: string): string {
  let hash = 0
  for (let i = 0; i < userId.length; i++) hash = (hash * 31 + userId.charCodeAt(i)) >>> 0
  return CURSOR_COLORS[hash % CURSOR_COLORS.length]
}

// ─── Markdown Converter ─────────────────────────────────────────────────────

function getTextFromInline(node: JSONContent): string {
  if (!node) return ''
  if (node.type === 'text') {
    let t = node.text || ''
    const marks = node.marks || []
    for (const mark of marks) {
      if (mark.type === 'bold') t = `**${t}**`
      else if (mark.type === 'italic') t = `*${t}*`
      else if (mark.type === 'code') t = `\`${t}\``
      else if (mark.type === 'strike') t = `~~${t}~~`
    }
    return t
  }
  if (node.type === 'hardBreak') return '\n'
  if (node.content) return node.content.map(getTextFromInline).join('')
  return ''
}

function jsonToMarkdown(doc: JSONContent): string {
  const lines: string[] = []

  function processNode(node: JSONContent, listIndent = 0) {
    if (!node) return
    switch (node.type) {
      case 'doc':
        node.content?.forEach((child) => processNode(child))
        break
      case 'heading': {
        const level = (node.attrs?.level as number) || 1
        const prefix = '#'.repeat(level)
        const text = node.content?.map(getTextFromInline).join('') || ''
        lines.push(`${prefix} ${text}`)
        lines.push('')
        break
      }
      case 'paragraph': {
        const text = node.content?.map(getTextFromInline).join('') || ''
        lines.push(text)
        lines.push('')
        break
      }
      case 'bulletList':
        node.content?.forEach((item) => processNode(item, listIndent))
        break
      case 'orderedList': {
        let idx = 1
        node.content?.forEach((item) => {
          if (item.type === 'listItem') {
            const text = item.content?.map((c) => {
              if (c.type === 'paragraph') return c.content?.map(getTextFromInline).join('') || ''
              return ''
            }).join('') || ''
            const indent = '  '.repeat(listIndent)
            lines.push(`${indent}${idx}. ${text}`)
            idx++
          }
        })
        lines.push('')
        break
      }
      case 'listItem': {
        const text = node.content?.map((c) => {
          if (c.type === 'paragraph') return c.content?.map(getTextFromInline).join('') || ''
          return ''
        }).join('') || ''
        const indent = '  '.repeat(listIndent)
        lines.push(`${indent}- ${text}`)
        break
      }
      case 'blockquote':
        node.content?.forEach((child) => {
          if (child.type === 'paragraph') {
            const text = child.content?.map(getTextFromInline).join('') || ''
            lines.push(`> ${text}`)
          } else {
            processNode(child)
          }
        })
        lines.push('')
        break
      case 'horizontalRule':
        lines.push('---')
        lines.push('')
        break
      case 'codeBlock': {
        const lang = (node.attrs?.language as string) || ''
        lines.push(`\`\`\`${lang}`)
        const text = node.content?.map(getTextFromInline).join('') || ''
        lines.push(text)
        lines.push('```')
        lines.push('')
        break
      }
      case 'table': {
        const rows = node.content || []
        rows.forEach((row, rowIdx) => {
          if (row.type === 'tableRow') {
            const cells = row.content || []
            const cellTexts = cells.map((cell) => {
              const text = cell.content?.map((c) => {
                if (c.type === 'paragraph') return c.content?.map(getTextFromInline).join('') || ''
                return ''
              }).join(' ') || ''
              return text
            })
            lines.push(`| ${cellTexts.join(' | ')} |`)
            if (rowIdx === 0) {
              lines.push(`| ${cellTexts.map(() => '---').join(' | ')} |`)
            }
          }
        })
        lines.push('')
        break
      }
      case 'image': {
        const src = (node.attrs?.src as string) || ''
        const alt = (node.attrs?.alt as string) || ''
        lines.push(`![${alt}](${src})`)
        lines.push('')
        break
      }
      default:
        if (node.content) {
          node.content.forEach((child) => processNode(child))
        }
    }
  }

  processNode(doc)
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n'
}

// ─── TOC Heading Type ────────────────────────────────────────────────────────

interface TocHeading {
  level: number
  text: string
  id: string
  index: number
}

// ─── Font Size & Color Presets ───────────────────────────────────────────────

const FONT_SIZES = [
  { label: '12', value: '12px' },
  { label: '14', value: '14px' },
  { label: '16', value: '16px' },
  { label: '18', value: '18px' },
  { label: '24', value: '24px' },
  { label: '36', value: '36px' },
]

const TEXT_COLORS = [
  { label: 'Black', value: '#000000' },
  { label: 'Red', value: '#dc2626' },
  { label: 'Blue', value: '#2563eb' },
  { label: 'Green', value: '#16a34a' },
  { label: 'Purple', value: '#9333ea' },
  { label: 'Orange', value: '#ea580c' },
]

const ZOOM_LEVELS = [75, 100, 125, 150]

// ─── Main Component ─────────────────────────────────────────────────────────

export default function DocEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [connectionStatus, setConnectionStatus] = useState<WebSocketStatus>(WebSocketStatus.Connecting)
  const [connectedUsers, setConnectedUsers] = useState<{ name: string; color: string }[]>([])
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const contentSeededRef = useRef(false)
  const importInputRef = useRef<HTMLInputElement>(null)

  // ─── Real-time collaboration (Hocuspocus) ────────────────────────────────
  // Y.Doc + provider are created once per mount via the lazy-ref pattern --
  // both are safe to construct synchronously (the provider just starts an
  // async connection attempt, like `new WebSocket(url)`). Torn down on
  // unmount below. If Hocuspocus is unreachable, the editor still works:
  // Collaboration binds to the local Y.Doc regardless of connection state,
  // and the REST autosave a few lines down keeps saving content_json as
  // it always has.
  const ydocRef = useRef<Y.Doc | null>(null)
  if (!ydocRef.current) {
    ydocRef.current = new Y.Doc()
  }
  const providerRef = useRef<HocuspocusProvider | null>(null)
  if (!providerRef.current && id) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    providerRef.current = new HocuspocusProvider({
      url: `${wsProtocol}//${window.location.host}/api/collaborate/${id}`,
      name: id,
      document: ydocRef.current,
      token: () => localStorage.getItem('access_token') || '',
    })
  }

  useEffect(() => {
    return () => {
      // Only the provider (a live network resource) is torn down here --
      // NOT the Y.Doc. useEditor() binds Collaboration to whichever Y.Doc
      // instance existed at editor-construction time and never re-reads
      // ydocRef afterwards (Tiptap only reacts to extension changes via an
      // explicit deps array, which this component doesn't use). Under React
      // StrictMode's dev-only double-invoke, destroying+recreating the
      // Y.Doc here left the editor permanently bound to an already-
      // destroyed Y.Doc while a second, live provider synced a different
      // one -- edits looked local-only forever. The Y.Doc itself holds no
      // network resource, so leaving it alone until the page genuinely
      // unmounts is safe.
      providerRef.current?.destroy()
      providerRef.current = null
    }
  }, [])

  useEffect(() => {
    const provider = providerRef.current
    if (!provider) return

    // No CollaborationCursor extension (see extensions list below) --
    // @tiptap/extension-collaboration-cursor@3.0.0 still targets the old
    // y-prosemirror sync plugin, incompatible with @tiptap/extension-
    // collaboration@3.20's newer @tiptap/y-tiptap engine (crashes on
    // mount). Presence/awareness still works without it -- set our own
    // local user field so other clients can show us in their
    // connectedUsers list.
    provider.awareness?.setLocalStateField('user', {
      name: user?.full_name || 'Anonymous',
      color: colorForUser(user?.id || 'anon'),
    })

    const handleStatus = ({ status }: { status: WebSocketStatus }) => setConnectionStatus(status)
    const handleAwarenessChange = () => {
      const states = provider.awareness?.getStates()
      if (!states) return
      const localClientId = provider.awareness?.clientID
      const others: { name: string; color: string }[] = []
      states.forEach((state: any, clientId: number) => {
        if (clientId === localClientId) return
        if (state?.user?.name) others.push({ name: state.user.name, color: state.user.color })
      })
      setConnectedUsers(others)
    }

    provider.on('status', handleStatus)
    provider.on('awarenessChange', handleAwarenessChange)
    handleAwarenessChange()

    // Belt-and-suspenders catch-up: the provider may already be connected
    // by the time this effect attaches (it's constructed eagerly during
    // render, before any effects run), so a 'status' event firing in that
    // window is missed and the pill would stick on "Connecting" forever
    // despite a genuinely working connection. A short poll is simpler and
    // more robust than chasing exact event-ordering guarantees across
    // React's dev-mode double-invoked effects.
    const pollId = window.setInterval(() => {
      // Read providerRef.current fresh (not the closed-over `provider`)
      // so this stays correct even if this effect instance is bound to an
      // earlier provider than the one currently live.
      const liveStatus = providerRef.current?.configuration?.websocketProvider?.status
      if (liveStatus) setConnectionStatus(liveStatus)
    }, 500)

    return () => {
      provider.off('status', handleStatus)
      provider.off('awarenessChange', handleAwarenessChange)
      window.clearInterval(pollId)
    }
  }, [providerRef.current, user?.id, user?.full_name])

  // UI state
  const [tocOpen, setTocOpen] = useState(true)
  const [findReplaceOpen, setFindReplaceOpen] = useState(false)
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [findResults, setFindResults] = useState<{ current: number; total: number }>({ current: 0, total: 0 })
  const [zoom, setZoom] = useState(100)
  const [showDownloadMenu, setShowDownloadMenu] = useState(false)
  const [showFontSizeMenu, setShowFontSizeMenu] = useState(false)
  const [showColorMenu, setShowColorMenu] = useState(false)
  const [tocHeadings, setTocHeadings] = useState<TocHeading[]>([])
  const [wordCount, setWordCount] = useState(0)
  const [rightPanel, setRightPanel] = useState<'none' | 'comments' | 'history'>('none')
  const [aiOpen, setAiOpen] = useState(false)
  const [aiSelectedText, setAiSelectedText] = useState('')

  const downloadMenuRef = useRef<HTMLDivElement>(null)
  const fontSizeMenuRef = useRef<HTMLDivElement>(null)
  const colorMenuRef = useRef<HTMLDivElement>(null)

  const { data: docData } = useQuery({
    queryKey: ['office-doc', id],
    queryFn: () => getOfficeDoc(id!),
    enabled: !!id,
  })

  const doc = docData?.data

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; content_json?: Record<string, unknown> }) => updateOfficeDoc(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  const starMutation = useMutation({
    mutationFn: () => starOfficeDoc(id!, !doc?.is_starred),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
    },
  })

  // ─── Tiptap Editor Setup ─────────────────────────────────────────────────

  const editor = useEditor({
    extensions: [
      // Collaboration's Y.UndoManager (via yUndoPlugin) replaces
      // StarterKit's local history -- it works identically whether or not
      // the Hocuspocus provider is actually connected, since undo/redo
      // operates on the local Y.Doc.
      StarterKit.configure({ history: false } as any),
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Highlight,
      Image,
      Placeholder.configure({ placeholder: 'Start typing...' }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      TextStyle,
      Color,
      FontSize,
      Collaboration.configure({ document: ydocRef.current }),
    ],
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none min-h-[500px] px-16 py-8',
      },
    },
    onUpdate: ({ editor: ed }) => {
      // Auto-save debounce
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        const json = ed.getJSON()
        updateMutation.mutate({ content_json: json as Record<string, unknown> })
      }, 2000)
      // Update word count + TOC
      updateWordCount(ed)
      updateToc(ed)
    },
  })

  // ─── Update Word Count ────────────────────────────────────────────────────

  const updateWordCount = useCallback((ed: ReturnType<typeof useEditor>) => {
    if (!ed) return
    const text = ed.getText()
    const trimmed = text.trim()
    const count = trimmed.length === 0 ? 0 : trimmed.split(/\s+/).length
    setWordCount(count)
  }, [])

  // ─── Update Table of Contents ─────────────────────────────────────────────

  const updateToc = useCallback((ed: ReturnType<typeof useEditor>) => {
    if (!ed) return
    const json = ed.getJSON()
    const headings: TocHeading[] = []
    let headingIndex = 0
    json.content?.forEach((node) => {
      if (node.type === 'heading' && node.attrs?.level) {
        const text = node.content?.map((c: any) => c.text || '').join('') || ''
        if (text.trim()) {
          headings.push({
            level: node.attrs.level as number,
            text,
            id: `heading-${headingIndex}`,
            index: headingIndex,
          })
        }
        headingIndex++
      }
    })
    setTocHeadings(headings)
  }, [])

  // ─── Load Initial Content ─────────────────────────────────────────────────
  // With Collaboration active, content lives in the Y.Doc -- calling
  // setContent unconditionally would stomp whatever other collaborators
  // already synced in. Only seed from the REST-loaded content_json if the
  // Y.Doc is genuinely empty (a brand-new document, or the very first time
  // this doc is opened after this feature shipped). A fallback timer covers
  // the case where Hocuspocus never connects at all -- the editor still
  // needs real content to show, not a permanently blank page.

  useEffect(() => {
    const provider = providerRef.current
    const ydoc = ydocRef.current
    if (!provider || !ydoc || !editor || !doc || contentSeededRef.current) return

    const trySeed = () => {
      if (contentSeededRef.current) return
      contentSeededRef.current = true

      const fragment = ydoc.getXmlFragment('default')
      if (fragment.length === 0 && doc.content_json && typeof doc.content_json === 'object') {
        editor.commands.setContent(doc.content_json)
      }
      setTimeout(() => {
        updateWordCount(editor)
        updateToc(editor)
      }, 100)
    }

    if (provider.isSynced) {
      trySeed()
      return
    }

    provider.on('synced', trySeed)
    const fallbackTimer = setTimeout(trySeed, 4000)
    return () => {
      provider.off('synced', trySeed)
      clearTimeout(fallbackTimer)
    }
  }, [editor, doc, updateWordCount, updateToc])

  // ─── Cleanup ──────────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  // ─── Keyboard Shortcut: Ctrl+H for Find & Replace ────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault()
        setFindReplaceOpen((prev) => !prev)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // ─── Close Dropdown Menus on Outside Click ────────────────────────────────

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (downloadMenuRef.current && !downloadMenuRef.current.contains(e.target as Node)) {
        setShowDownloadMenu(false)
      }
      if (fontSizeMenuRef.current && !fontSizeMenuRef.current.contains(e.target as Node)) {
        setShowFontSizeMenu(false)
      }
      if (colorMenuRef.current && !colorMenuRef.current.contains(e.target as Node)) {
        setShowColorMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // ─── Title Change ─────────────────────────────────────────────────────────

  const handleTitleChange = useCallback(
    (title: string) => {
      updateMutation.mutate({ title })
    },
    [updateMutation]
  )

  // ─── Find & Replace ──────────────────────────────────────────────────────

  const handleFind = useCallback(() => {
    if (!editor || !findText) {
      setFindResults({ current: 0, total: 0 })
      return
    }
    const text = editor.getText()
    const regex = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    const matches = text.match(regex)
    setFindResults({ current: matches ? 1 : 0, total: matches?.length || 0 })
  }, [editor, findText])

  const handleReplace = useCallback(() => {
    if (!editor || !findText) return
    const { state } = editor
    const { from, to } = state.selection
    const selectedText = state.doc.textBetween(from, to)

    if (selectedText.toLowerCase() === findText.toLowerCase()) {
      editor.chain().focus().deleteSelection().insertContent(replaceText).run()
    }
    // Try to find next occurrence
    handleFind()
  }, [editor, findText, replaceText, handleFind])

  const handleReplaceAll = useCallback(() => {
    if (!editor || !findText) return
    const content = editor.getHTML()
    const regex = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    const newContent = content.replace(regex, replaceText)
    editor.commands.setContent(newContent)
    setFindResults({ current: 0, total: 0 })
  }, [editor, findText, replaceText])

  // ─── Scroll to Heading (TOC) ─────────────────────────────────────────────

  const scrollToHeading = useCallback((headingIndex: number) => {
    if (!editor) return
    const editorElement = editor.view.dom
    const headings = editorElement.querySelectorAll('h1, h2, h3')
    if (headings[headingIndex]) {
      headings[headingIndex].scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [editor])

  // ─── Export: DOCX ─────────────────────────────────────────────────────────

  const exportDocx = useCallback(async () => {
    if (!id) return
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`/api/office/${id}/export/docx`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${doc?.title || 'document'}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('DOCX export error:', err)
    }
    setShowDownloadMenu(false)
  }, [id, doc?.title])

  // ─── Export: PDF ──────────────────────────────────────────────────────────

  const exportPdf = useCallback(() => {
    if (!id) return
    const token = localStorage.getItem('access_token')
    window.open(`/api/office/${id}/export/pdf?token=${token}`, '_blank')
    setShowDownloadMenu(false)
  }, [id])

  // ─── Export: Markdown ─────────────────────────────────────────────────────

  const exportMarkdown = useCallback(() => {
    if (!editor) return
    const json = editor.getJSON()
    const md = jsonToMarkdown(json)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc?.title || 'document'}.md`
    a.click()
    URL.revokeObjectURL(url)
    setShowDownloadMenu(false)
  }, [editor, doc?.title])

  // ─── Import: DOCX ────────────────────────────────────────────────────────

  const handleImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !id) return
    try {
      const token = localStorage.getItem('access_token')
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`/api/office/${id}/import`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (!res.ok) throw new Error('Import failed')
      // Refresh doc content
      queryClient.invalidateQueries({ queryKey: ['office-doc', id] })
      // Reset file input
      if (importInputRef.current) importInputRef.current.value = ''
      // Reload content into editor
      const result = await res.json()
      if (result?.data?.content_json && editor) {
        editor.commands.setContent(result.data.content_json)
      }
    } catch (err) {
      console.error('Import error:', err)
    }
  }, [id, queryClient, editor])

  // ─── Font Size Handler ────────────────────────────────────────────────────

  const handleFontSize = useCallback((size: string) => {
    if (!editor) return
    editor.chain().focus().setFontSize(size).run()
    setShowFontSizeMenu(false)
  }, [editor])

  // ─── Color Handler ────────────────────────────────────────────────────────

  const handleColor = useCallback((color: string) => {
    if (!editor) return
    editor.chain().focus().setColor(color).run()
    setShowColorMenu(false)
  }, [editor])

  // ─── AI Assist ────────────────────────────────────────────────────────────

  const openAiAssist = useCallback(() => {
    if (!editor) return
    const { from, to } = editor.state.selection
    const text = from !== to ? editor.state.doc.textBetween(from, to, ' ') : ''
    setAiSelectedText(text)
    setAiOpen(true)
  }, [editor])

  const handleAiReplaceSelection = useCallback((text: string) => {
    if (!editor) return
    editor.chain().focus().deleteSelection().insertContent(text).run()
  }, [editor])

  const handleAiInsert = useCallback((text: string) => {
    if (!editor) return
    editor.chain().focus().insertContent(text).run()
  }, [editor])

  const handleVersionRestored = useCallback((contentJson: Record<string, unknown>) => {
    if (!editor) return
    editor.commands.setContent(contentJson)
  }, [editor])

  // ─── Zoom Style ───────────────────────────────────────────────────────────

  const zoomStyle = useMemo(() => ({
    transform: `scale(${zoom / 100})`,
    transformOrigin: 'top center',
    width: `${10000 / zoom}%`,
  }), [zoom])

  if (!id) return null

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] bg-gray-100 dark:bg-gray-800">
      {/* ─── Top Bar ─────────────────────────────────────────────────────── */}
      <EditorTopBar
        docType="document"
        docId={id}
        title={doc?.title || 'Untitled document'}
        isStarred={doc?.is_starred ?? false}
        onTitleChange={handleTitleChange}
        onStar={() => starMutation.mutate()}
        connectedUsers={connectedUsers}
        connectionStatus={connectionStatus}
        onReadView={() => navigate(`/docs/${id}/read`)}
      />

      {/* ─── Primary Toolbar (DocToolbar) ────────────────────────────────── */}
      <DocToolbar editor={editor} />

      {/* ─── Extended Toolbar ────────────────────────────────────────────── */}
      <div className="bg-white dark:bg-gray-900 border-b px-3 py-1.5 flex items-center gap-2 flex-wrap">
        {/* Font Size Selector */}
        <div className="relative" ref={fontSizeMenuRef}>
          <button
            onClick={() => setShowFontSizeMenu(!showFontSizeMenu)}
            className="flex items-center gap-1 px-2 py-1 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Font Size
            <ChevronDown className="h-3 w-3" />
          </button>
          {showFontSizeMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-md shadow-lg z-50 py-1 min-w-[80px]">
              {FONT_SIZES.map((fs) => (
                <button
                  key={fs.value}
                  onClick={() => handleFontSize(fs.value)}
                  className="block w-full text-left px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  {fs.label}px
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Text Color Picker */}
        <div className="relative" ref={colorMenuRef}>
          <button
            onClick={() => setShowColorMenu(!showColorMenu)}
            className="flex items-center gap-1 px-2 py-1 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <span
              className="inline-block w-3 h-3 rounded-full border border-gray-400"
              style={{ backgroundColor: editor?.getAttributes('textStyle')?.color || '#000000' }}
            />
            Color
            <ChevronDown className="h-3 w-3" />
          </button>
          {showColorMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-md shadow-lg z-50 py-1 min-w-[120px]">
              {TEXT_COLORS.map((c) => (
                <button
                  key={c.value}
                  onClick={() => handleColor(c.value)}
                  className="flex items-center gap-2 w-full text-left px-3 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <span
                    className="inline-block w-3 h-3 rounded-full border border-gray-400"
                    style={{ backgroundColor: c.value }}
                  />
                  {c.label}
                </button>
              ))}
              <div className="border-t dark:border-gray-700 mt-1 pt-1">
                <button
                  onClick={() => {
                    editor?.chain().focus().unsetColor().run()
                    setShowColorMenu(false)
                  }}
                  className="block w-full text-left px-3 py-1 text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  Remove color
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />

        {/* Download Dropdown */}
        <div className="relative" ref={downloadMenuRef}>
          <button
            onClick={() => setShowDownloadMenu(!showDownloadMenu)}
            className="flex items-center gap-1 px-2 py-1 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download
            <ChevronDown className="h-3 w-3" />
          </button>
          {showDownloadMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-md shadow-lg z-50 py-1 min-w-[140px]">
              <button
                onClick={exportDocx}
                className="block w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                DOCX (.docx)
              </button>
              <button
                onClick={exportPdf}
                className="block w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                PDF (.pdf)
              </button>
              <button
                onClick={exportMarkdown}
                className="block w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                Markdown (.md)
              </button>
            </div>
          )}
        </div>

        {/* Import Button */}
        <button
          onClick={() => importInputRef.current?.click()}
          className="flex items-center gap-1 px-2 py-1 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
          Import
        </button>
        <input
          ref={importInputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={handleImport}
        />

        <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />

        {/* Find & Replace Toggle */}
        <button
          onClick={() => setFindReplaceOpen(!findReplaceOpen)}
          className={`flex items-center gap-1 px-2 py-1 text-sm rounded-md border transition-colors ${
            findReplaceOpen
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
          }`}
          title="Find & Replace (Ctrl+H)"
        >
          <Search className="h-3.5 w-3.5" />
          Find
        </button>

        {/* Ask AI */}
        <button
          onClick={openAiAssist}
          className="flex items-center gap-1 px-2 py-1 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          title="Ask AI"
        >
          <Sparkles className="h-3.5 w-3.5 text-blue-500" />
          Ask AI
        </button>

        <div className="flex-1" />

        {/* Comments Toggle */}
        <button
          onClick={() => setRightPanel(rightPanel === 'comments' ? 'none' : 'comments')}
          className={`flex items-center gap-1 px-2 py-1 text-sm rounded-md border transition-colors ${
            rightPanel === 'comments'
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
          }`}
          title="Toggle Comments"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Comments
        </button>

        {/* Version History Toggle */}
        <button
          onClick={() => setRightPanel(rightPanel === 'history' ? 'none' : 'history')}
          className={`flex items-center gap-1 px-2 py-1 text-sm rounded-md border transition-colors ${
            rightPanel === 'history'
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
          }`}
          title="Toggle Version History"
        >
          <History className="h-3.5 w-3.5" />
          History
        </button>

        {/* TOC Toggle */}
        <button
          onClick={() => setTocOpen(!tocOpen)}
          className={`flex items-center gap-1 px-2 py-1 text-sm rounded-md border transition-colors ${
            tocOpen
              ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
          }`}
          title="Toggle Table of Contents"
        >
          {tocOpen ? <PanelLeftClose className="h-3.5 w-3.5" /> : <ListTree className="h-3.5 w-3.5" />}
          TOC
        </button>
      </div>

      {/* ─── Find & Replace Bar ──────────────────────────────────────────── */}
      {findReplaceOpen && (
        <div className="bg-white dark:bg-gray-900 border-b px-4 py-2 flex items-center gap-2 flex-wrap shadow-sm">
          <Search className="h-4 w-4 text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Find..."
            value={findText}
            onChange={(e) => setFindText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleFind()}
            className="px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-transparent text-gray-900 dark:text-gray-100 w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="Replace with..."
            value={replaceText}
            onChange={(e) => setReplaceText(e.target.value)}
            className="px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-transparent text-gray-900 dark:text-gray-100 w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            onClick={handleFind}
            className="px-2 py-1 text-xs font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Find
          </button>
          <button
            onClick={handleReplace}
            className="px-2 py-1 text-xs font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Replace
          </button>
          <button
            onClick={handleReplaceAll}
            className="px-2 py-1 text-xs font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            Replace All
          </button>
          {findResults.total > 0 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {findResults.current} of {findResults.total} matches
            </span>
          )}
          <button
            onClick={() => {
              setFindReplaceOpen(false)
              setFindText('')
              setReplaceText('')
              setFindResults({ current: 0, total: 0 })
            }}
            className="ml-auto p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* ─── Main Content Area ───────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ─── Table of Contents Sidebar ───────────────────────────────── */}
        {tocOpen && (
          <div className="w-56 shrink-0 bg-white dark:bg-gray-900 border-r dark:border-gray-700 overflow-y-auto">
            <div className="px-3 py-2 border-b dark:border-gray-700 flex items-center gap-2">
              <ListTree className="h-4 w-4 text-gray-500 dark:text-gray-400" />
              <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wide">
                Table of Contents
              </span>
            </div>
            {tocHeadings.length === 0 ? (
              <div className="px-3 py-4 text-xs text-gray-400 dark:text-gray-500 italic">
                Add headings (H1, H2, H3) to see them here.
              </div>
            ) : (
              <nav className="py-1">
                {tocHeadings.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => scrollToHeading(h.index)}
                    className={`block w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 truncate transition-colors ${
                      h.level === 1 ? 'font-semibold' : h.level === 2 ? 'pl-7' : 'pl-11 text-xs'
                    }`}
                    title={h.text}
                  >
                    {h.level === 1 && <ChevronRight className="inline h-3 w-3 mr-1 text-gray-400" />}
                    {h.text}
                  </button>
                ))}
              </nav>
            )}
          </div>
        )}

        {/* ─── Editor Area ─────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto" id="editor-scroll-container">
          <div style={zoomStyle}>
            <div className="max-w-[850px] mx-auto my-6 bg-white dark:bg-gray-900 shadow-sm rounded-sm min-h-[1100px] border dark:border-gray-700">
              <EditorContent editor={editor} />
            </div>
          </div>
        </div>

        {/* ─── Right Panel: Comments / Version History ────────────────── */}
        {rightPanel === 'comments' && <CommentsPanel docId={id} />}
        {rightPanel === 'history' && (
          <VersionHistoryPanel docId={id} onRestored={handleVersionRestored} />
        )}
      </div>

      {/* ─── Bottom Status Bar ───────────────────────────────────────────── */}
      <div className="bg-white dark:bg-gray-900 border-t dark:border-gray-700 px-4 py-1.5 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
        {/* Word Count */}
        <span>
          {wordCount} {wordCount === 1 ? 'word' : 'words'}
        </span>

        <div className="w-px h-4 bg-gray-200 dark:bg-gray-700" />

        {/* Save Status */}
        <span>
          {updateMutation.isPending ? 'Saving...' : 'Saved'}
        </span>

        <div className="flex-1" />

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.max(75, z - 25))}
            disabled={zoom <= 75}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <select
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="bg-transparent text-xs text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 focus:outline-none"
          >
            {ZOOM_LEVELS.map((z) => (
              <option key={z} value={z}>
                {z}%
              </option>
            ))}
          </select>
          <button
            onClick={() => setZoom((z) => Math.min(150, z + 25))}
            disabled={zoom >= 150}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ─── AI Assist Popover ──────────────────────────────────────────── */}
      <AiAssistPopover
        docId={id}
        selectedText={aiSelectedText}
        isOpen={aiOpen}
        onClose={() => setAiOpen(false)}
        onReplaceSelection={handleAiReplaceSelection}
        onInsert={handleAiInsert}
      />

      {/* ─── Styles ──────────────────────────────────────────────────────── */}
      <style>{`
        .ProseMirror {
          min-height: 1000px;
          padding: 60px 70px;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: #adb5bd;
          pointer-events: none;
          height: 0;
        }
        .ProseMirror table {
          border-collapse: collapse;
          margin: 1em 0;
          width: 100%;
        }
        .ProseMirror td, .ProseMirror th {
          border: 1px solid #d1d5db;
          padding: 8px 12px;
          vertical-align: top;
        }
        .ProseMirror th {
          background-color: #f3f4f6;
          font-weight: 600;
        }
        .ProseMirror img {
          max-width: 100%;
          height: auto;
        }
        .ProseMirror blockquote {
          border-left: 3px solid #d1d5db;
          padding-left: 1em;
          color: #6b7280;
        }
        .ProseMirror mark {
          background-color: #fef08a;
          padding: 0.125em 0;
        }
        .ProseMirror h1 {
          font-size: 2em;
          font-weight: 700;
          margin: 0.67em 0;
        }
        .ProseMirror h2 {
          font-size: 1.5em;
          font-weight: 600;
          margin: 0.75em 0;
        }
        .ProseMirror h3 {
          font-size: 1.17em;
          font-weight: 600;
          margin: 0.83em 0;
        }

        /* Print Styles */
        @media print {
          body * {
            visibility: hidden;
          }
          #editor-scroll-container,
          #editor-scroll-container * {
            visibility: visible;
          }
          #editor-scroll-container {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
          }
          #editor-scroll-container .ProseMirror {
            min-height: 0;
            padding: 0;
            border: none;
            box-shadow: none;
          }
          .ProseMirror table {
            page-break-inside: avoid;
          }
          .ProseMirror img {
            page-break-inside: avoid;
            max-width: 100%;
          }
          .ProseMirror h1, .ProseMirror h2, .ProseMirror h3 {
            page-break-after: avoid;
          }
          .ProseMirror blockquote {
            border-left-color: #999;
            color: #333;
          }
        }

        /* Dark mode overrides for ProseMirror */
        .dark .ProseMirror th {
          background-color: #374151;
          color: #e5e7eb;
        }
        .dark .ProseMirror td {
          border-color: #4b5563;
        }
        .dark .ProseMirror th {
          border-color: #4b5563;
        }
        .dark .ProseMirror blockquote {
          border-left-color: #4b5563;
          color: #9ca3af;
        }
        .dark .ProseMirror mark {
          background-color: #854d0e;
          color: #fef08a;
        }
      `}</style>
    </div>
  )
}
