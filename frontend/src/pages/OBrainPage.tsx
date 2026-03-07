import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowLeft, Send, Sparkles, Loader2, Plus, Trash2,
  Database, PanelLeftClose, PanelLeft, Paperclip, X, FileIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  chatStream,
  listConversations,
  getConversation,
  deleteConversation,
  type Conversation,
} from '@/api/brain'

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools?: string[]
  sources?: Array<{ tool: string; count: number }>
  isStreaming?: boolean
  files?: Array<{ name: string; size: number }>
}

function ToolBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-1.5 py-0.5 rounded-full font-medium">
      <Database className="h-2.5 w-2.5" />
      {name.replace('query_', '').replace('search_', '')}
    </span>
  )
}

function SourcesBadge({ sources }: { sources: Array<{ tool: string; count: number }> }) {
  const total = sources.reduce((sum, s) => sum + s.count, 0)
  return (
    <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1">
      Based on {total} record{total !== 1 ? 's' : ''} from {sources.map((s) => s.tool.replace('query_', '')).join(', ')}
    </p>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export default function OBrainPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [isDragging, setIsDragging] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Streaming refs — accumulate tokens without triggering React renders,
  // then flush to state at ~60fps via requestAnimationFrame.
  const streamBufferRef = useRef('')
  const rafIdRef = useRef<number | null>(null)

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (el) {
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }, [])

  const { data: conversationsData } = useQuery({
    queryKey: ['brain-conversations'],
    queryFn: () => listConversations(50),
  })
  const conversations: Conversation[] = conversationsData?.data ?? []

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return
    const userText = input.trim()
    setInput('')

    const fileNames = attachedFiles.map((f) => ({ name: f.name, size: f.size }))

    // Upload files first
    const uploadedFileIds: string[] = []
    for (const file of attachedFiles) {
      try {
        const fd = new FormData()
        fd.append('file', file)
        if (conversationId) fd.append('conversation_id', conversationId)
        const token = localStorage.getItem('access_token')
        const resp = await fetch('/api/brain/chat/upload', {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: fd,
        })
        if (resp.ok) {
          const data = await resp.json()
          uploadedFileIds.push(data.data.id)
          if (data.data.conversation_id && !conversationId) {
            setConversationId(data.data.conversation_id)
          }
        }
      } catch {
        // Skip failed uploads
      }
    }
    setAttachedFiles([])

    const userMsg: DisplayMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      files: fileNames.length > 0 ? fileNames : undefined,
    }

    const assistantMsg: DisplayMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      tools: [],
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)
    requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }))

    // Flush buffered tokens to React state at ~60fps
    const flushBuffer = () => {
      const chunk = streamBufferRef.current
      if (chunk) {
        streamBufferRef.current = ''
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'assistant') last.content += chunk
          return [...updated]
        })
      }
      rafIdRef.current = requestAnimationFrame(flushBuffer)
    }
    rafIdRef.current = requestAnimationFrame(flushBuffer)

    try {
      for await (const event of chatStream(
        userText,
        conversationId,
        'O-Brain Full Screen',
        uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
      )) {
        if (event.type === 'text' && event.content) {
          // Accumulate in ref — the RAF loop pushes to state at 60fps
          streamBufferRef.current += event.content
        } else if (event.type === 'tool_use' && event.tool) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') last.tools = [...(last.tools || []), event.tool!]
            return [...updated]
          })
        } else if (event.type === 'sources' && event.sources) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') last.sources = event.sources
            return [...updated]
          })
        } else if (event.type === 'done') {
          // Final flush of any remaining buffered text
          if (streamBufferRef.current) {
            const remaining = streamBufferRef.current
            streamBufferRef.current = ''
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last.role === 'assistant') last.content += remaining
              return [...updated]
            })
          }
          if (event.conversation_id) setConversationId(event.conversation_id)
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') last.isStreaming = false
            return [...updated]
          })
          queryClient.invalidateQueries({ queryKey: ['brain-conversations'] })
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'assistant') {
          last.content = 'Sorry, something went wrong. Please try again.'
          last.isStreaming = false
        }
        return [...updated]
      })
    } finally {
      // Stop the RAF flush loop
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
      streamBufferRef.current = ''
      setIsStreaming(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setConversationId(null)
    setAttachedFiles([])
  }

  const handleLoadConversation = async (conv: Conversation) => {
    try {
      const resp = await getConversation(conv.id)
      const detail = resp.data
      setConversationId(detail.id)
      setMessages(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          tools: m.tools_used ?? undefined,
          sources: m.sources ?? undefined,
        })),
      )
    } catch {
      // Failed to load
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await deleteConversation(id)
    queryClient.invalidateQueries({ queryKey: ['brain-conversations'] })
    if (conversationId === id) handleNewChat()
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setAttachedFiles((prev) => [...prev, ...files])
    e.target.value = ''
  }

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    setAttachedFiles((prev) => [...prev, ...files])
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-[280px] bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col shrink-0">
          <div className="p-3 border-b border-gray-100 dark:border-gray-700">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleLoadConversation(conv)}
                className={cn(
                  'w-full text-left px-3 py-2.5 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors group',
                  conversationId === conv.id && 'bg-purple-50/50 dark:bg-purple-900/20',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{conv.title}</p>
                    <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                      {conv.message_count} msg{conv.message_count !== 1 ? 's' : ''} · {new Date(conv.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition shrink-0"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div
        className="flex-1 flex flex-col min-w-0"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => navigate('/')}
            className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
            title="Back to app"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
            title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            {sidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeft className="h-5 w-5" />}
          </button>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-500" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">O-Brain</h1>
          </div>
        </div>

        {/* Drag overlay */}
        {isDragging && (
          <div className="absolute inset-0 z-50 bg-purple-500/10 border-2 border-dashed border-purple-400 flex items-center justify-center pointer-events-none">
            <div className="bg-white dark:bg-gray-900 rounded-xl px-6 py-4 shadow-lg">
              <p className="text-purple-600 dark:text-purple-400 font-medium">Drop files to attach</p>
            </div>
          </div>
        )}

        {/* Messages */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <Sparkles className="h-16 w-16 text-purple-300 dark:text-purple-700 mb-6" />
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Welcome to O-Brain</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md">
                  Your AI business assistant. Ask about clients, finances, proposals, meetings — anything in your business data.
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div className={cn(
                  'max-w-[75%] rounded-2xl px-5 py-3 text-sm',
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-md shadow-sm',
                )}>
                  {/* Attached files */}
                  {msg.files && msg.files.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {msg.files.map((f, i) => (
                        <span key={i} className="inline-flex items-center gap-1 text-xs bg-blue-500/20 text-blue-100 px-2 py-0.5 rounded">
                          <FileIcon className="h-3 w-3" />
                          {f.name}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Tool badges */}
                  {msg.tools && msg.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {msg.tools.map((t, i) => <ToolBadge key={i} name={t} />)}
                    </div>
                  )}
                  {/* Content */}
                  {msg.content ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_pre]:my-1 [&_code]:text-xs [&_pre]:text-xs [&_pre]:bg-gray-100 [&_pre]:dark:bg-gray-800 [&_pre]:rounded [&_pre]:p-2">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : null}
                  {msg.isStreaming && !msg.content && (
                    <div className="flex items-center gap-1 py-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:0ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:300ms]" />
                    </div>
                  )}
                  {msg.isStreaming && msg.content && (
                    <span className="inline-block w-1.5 h-4 bg-gray-400 dark:bg-gray-500 animate-pulse ml-0.5 align-text-bottom" />
                  )}
                  {msg.sources && msg.sources.length > 0 && <SourcesBadge sources={msg.sources} />}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* File chips */}
        {attachedFiles.length > 0 && (
          <div className="px-4 py-2 bg-white dark:bg-gray-900 border-t border-gray-100 dark:border-gray-700">
            <div className="max-w-3xl mx-auto flex flex-wrap gap-2">
              {attachedFiles.map((file, i) => (
                <span key={i} className="inline-flex items-center gap-1.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2.5 py-1 rounded-full">
                  <FileIcon className="h-3 w-3" />
                  {file.name}
                  <span className="text-gray-400">({formatFileSize(file.size)})</span>
                  <button onClick={() => removeFile(i)} className="p-0.5 hover:text-red-500">
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="px-4 py-4 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
          <div className="max-w-3xl mx-auto flex items-center gap-3 bg-gray-50 dark:bg-gray-800 rounded-xl px-4 py-3">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
              title="Attach file"
            >
              <Paperclip className="h-5 w-5" />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask O-Brain anything about your business..."
              disabled={isStreaming}
              className="flex-1 bg-transparent text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="p-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-30 transition"
            >
              {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
