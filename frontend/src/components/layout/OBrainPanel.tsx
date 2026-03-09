import { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  X, Send, Sparkles, Loader2, MessageSquare, Plus, Trash2,
  AlertCircle, ChevronLeft, Database, Maximize2, Newspaper, RefreshCw, ExternalLink,
} from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import {
  chatStream,
  listConversations,
  getConversation,
  deleteConversation,
  listAlerts,
  markAlertRead,
  listKnowledge,
  listNewsArticles,
  refreshNews,
  type Conversation,
  type BrainAlert,
  type NewsArticle,
} from '@/api/brain'

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools?: string[]
  sources?: Array<{ tool: string; count: number }>
  isStreaming?: boolean
}

type PanelView = 'chat' | 'history' | 'alerts' | 'news'

function getPageContext(pathname: string): string {
  const segments = pathname.split('/').filter(Boolean)
  if (segments.length === 0) return 'Dashboard'
  const labels: Record<string, string> = {
    contacts: 'Contacts', invoices: 'Invoices', proposals: 'Proposals',
    expenses: 'Expenses', cashbook: 'Cashbook', income: 'Income',
    reports: 'Reports', scheduling: 'Scheduling', workflows: 'Workflows',
    forms: 'Forms', conversations: 'Conversations', pipelines: 'Pipelines',
    drive: 'Drive', meetings: 'Meetings', settings: 'Settings',
    budgets: 'Budgets', estimates: 'Estimates', docs: 'Docs',
    sheets: 'Sheets', slides: 'Slides', recordings: 'Recordings',
  }
  const page = labels[segments[0]] || segments[0].charAt(0).toUpperCase() + segments[0].slice(1)
  return segments.length > 1 ? `${page} > ${segments[1].slice(0, 12)}` : page
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

export default function OBrainPanel() {
  const { panelState, closePanel, isMobile } = useUiStore()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [view, setView] = useState<PanelView>('chat')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  // Token queue — buffer incoming tokens and release at natural reading pace
  const tokenQueueRef = useRef<string[]>([])
  const isProcessingRef = useRef(false)
  const drainTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (el) {
      // Only auto-scroll if user is near bottom (within 120px)
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }, [])

  const { data: conversationsData } = useQuery({
    queryKey: ['brain-conversations'],
    queryFn: () => listConversations(20),
    enabled: panelState === 'obrain' && view === 'history',
  })

  const { data: alertsData } = useQuery({
    queryKey: ['brain-alerts'],
    queryFn: () => listAlerts(true, 10),
    enabled: panelState === 'obrain',
    refetchInterval: 60000,
  })

  const conversations: Conversation[] = conversationsData?.data ?? []
  const alerts: BrainAlert[] = alertsData?.data ?? []

  // Check discovery progress via knowledge base
  const { data: knowledgeData } = useQuery({
    queryKey: ['brain-knowledge-discovery'],
    queryFn: () => listKnowledge(1, 100, 'discovery'),
    enabled: panelState === 'obrain',
  })
  const discoveryProgress = Math.min(100, Math.round(((knowledgeData?.data?.items?.length ?? 0) / 28) * 100))
  const [discoveryDismissed, setDiscoveryDismissed] = useState(false)

  // News
  const [newsFilter, setNewsFilter] = useState('all')
  const [newsRefreshing, setNewsRefreshing] = useState(false)
  const { data: newsData, refetch: refetchNews } = useQuery({
    queryKey: ['brain-news', newsFilter],
    queryFn: () => listNewsArticles(newsFilter !== 'all' ? newsFilter : undefined, 20),
    enabled: panelState === 'obrain' && view === 'news',
  })
  const newsArticles: NewsArticle[] = newsData?.data ?? []

  const handleRefreshNews = async () => {
    setNewsRefreshing(true)
    try {
      await refreshNews()
      await refetchNews()
    } finally {
      setNewsRefreshing(false)
    }
  }

  const handleDiscussArticle = (article: NewsArticle) => {
    setView('chat')
    handleSend(`Tell me more about this news article: "${article.title}" from ${article.source}. ${article.summary || ''}`)
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  if (panelState !== 'obrain') return null

  const handleSend = async (directMessage?: string) => {
    const text = directMessage || input.trim()
    if (!text || isStreaming) return
    const userText = text
    if (!directMessage) setInput('')

    const userMsg: DisplayMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
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
    // Force scroll to bottom when sending
    requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }))

    // Drain token queue at natural reading pace (~35ms per token)
    const drainQueue = () => {
      if (tokenQueueRef.current.length === 0) {
        isProcessingRef.current = false
        return
      }
      isProcessingRef.current = true
      const token = tokenQueueRef.current.shift()!
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'assistant') last.content += token
        return [...updated]
      })
      drainTimerRef.current = setTimeout(drainQueue, 35)
    }

    const enqueueToken = (text: string) => {
      tokenQueueRef.current.push(text)
      if (!isProcessingRef.current) drainQueue()
    }

    try {
      const context = getPageContext(location.pathname)
      for await (const event of chatStream(userText, conversationId, context)) {
        if (event.type === 'text' && event.content) {
          enqueueToken(event.content)
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
          // Flush remaining tokens immediately
          if (tokenQueueRef.current.length > 0) {
            const remaining = tokenQueueRef.current.join('')
            tokenQueueRef.current = []
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
      if (drainTimerRef.current) clearTimeout(drainTimerRef.current)
      drainTimerRef.current = null
      tokenQueueRef.current = []
      isProcessingRef.current = false
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
    setView('chat')
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
      setView('chat')
    } catch {
      // Failed to load
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await deleteConversation(id)
    queryClient.invalidateQueries({ queryKey: ['brain-conversations'] })
    if (conversationId === id) {
      handleNewChat()
    }
  }

  const handleAlertClick = async (alert: BrainAlert) => {
    if (!alert.is_read) {
      await markAlertRead(alert.id)
      queryClient.invalidateQueries({ queryKey: ['brain-alerts'] })
    }
  }

  const contextLabel = getPageContext(location.pathname)

  const panel = (
    <aside className={cn(
      'bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 flex flex-col',
      isMobile ? 'fixed inset-0 z-50 w-full' : 'w-[340px] min-h-screen',
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {view !== 'chat' && (
            <button
              onClick={() => setView('chat')}
              className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {view === 'history' ? 'Conversations' : view === 'alerts' ? 'Alerts' : view === 'news' ? 'News' : 'O-Brain'}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          {view === 'chat' && (
            <>
              <button
                onClick={handleNewChat}
                className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="New conversation"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                onClick={() => { closePanel(); navigate('/brain') }}
                className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Full screen"
              >
                <Maximize2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => setView('history')}
                className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Conversation history"
              >
                <MessageSquare className="h-4 w-4" />
              </button>
              <button
                onClick={() => setView('news')}
                className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="News"
              >
                <Newspaper className="h-4 w-4" />
              </button>
              <button
                onClick={() => setView('alerts')}
                className="relative p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Alerts"
              >
                <AlertCircle className="h-4 w-4" />
                {alerts.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 h-3.5 w-3.5 bg-red-500 text-white text-[8px] rounded-full flex items-center justify-center font-bold">
                    {alerts.length > 9 ? '9+' : alerts.length}
                  </span>
                )}
              </button>
            </>
          )}
          <button
            onClick={closePanel}
            className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* History View */}
      {view === 'history' && (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {conversations.length === 0 ? (
            <p className="text-center text-sm text-gray-400 dark:text-gray-500 py-12">No conversations yet</p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleLoadConversation(conv)}
                className={cn(
                  'w-full text-left px-4 py-3 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors group',
                  conversationId === conv.id && 'bg-purple-50/50 dark:bg-purple-900/20',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{conv.title}</p>
                    <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                      {conv.message_count} message{conv.message_count !== 1 ? 's' : ''} · {new Date(conv.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* Alerts View */}
      {view === 'alerts' && (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {alerts.length === 0 ? (
            <p className="text-center text-sm text-gray-400 dark:text-gray-500 py-12">No new alerts</p>
          ) : (
            alerts.map((alert) => (
              <button
                key={alert.id}
                onClick={() => handleAlertClick(alert)}
                className="w-full text-left px-4 py-3 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <AlertCircle className={cn(
                    'h-4 w-4 mt-0.5 shrink-0',
                    alert.is_read ? 'text-gray-300' : 'text-amber-500',
                  )} />
                  <div>
                    <p className={cn(
                      'text-sm',
                      alert.is_read ? 'text-gray-500' : 'text-gray-900 dark:text-gray-100 font-medium',
                    )}>{alert.title}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 line-clamp-2">{alert.message}</p>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* News View */}
      {view === 'news' && (
        <div className="flex-1 overflow-y-auto scrollbar-thin flex flex-col">
          {/* Filter pills + refresh */}
          <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-700 flex items-center gap-2">
            <div className="flex gap-1 flex-1 overflow-x-auto">
              {[
                { key: 'all', label: 'All' },
                { key: 'industry', label: 'My Industry' },
                { key: 'local', label: 'Local' },
                { key: 'topic', label: 'AI & Tech' },
              ].map((f) => (
                <button
                  key={f.key}
                  onClick={() => setNewsFilter(f.key)}
                  className={cn(
                    'px-2.5 py-1 rounded-full text-[11px] font-medium whitespace-nowrap transition-colors',
                    newsFilter === f.key
                      ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                      : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <button
              onClick={handleRefreshNews}
              disabled={newsRefreshing}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"
              title="Refresh news"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', newsRefreshing && 'animate-spin')} />
            </button>
          </div>

          {/* Articles */}
          <div className="flex-1 overflow-y-auto">
            {newsArticles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
                <Newspaper className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">No news articles yet</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">Set your preferences in Settings &gt; News</p>
                <button
                  onClick={handleRefreshNews}
                  disabled={newsRefreshing}
                  className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
                >
                  {newsRefreshing ? 'Fetching...' : 'Fetch articles now'}
                </button>
              </div>
            ) : (
              newsArticles.map((article) => (
                <div
                  key={article.id}
                  className="px-4 py-3 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-2 leading-snug">
                        {article.title}
                      </p>
                      <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                        {article.source}
                        {article.published_at && (
                          <> &middot; {new Date(article.published_at).toLocaleDateString()}</>
                        )}
                      </p>
                      {article.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{article.summary}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2">
                        <button
                          onClick={() => handleDiscussArticle(article)}
                          className="text-[11px] font-medium text-purple-600 dark:text-purple-400 hover:underline"
                        >
                          Discuss with O-Brain
                        </button>
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-0.5 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                        >
                          Read <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Chat View */}
      {view === 'chat' && (
        <>
          {/* Compact discovery banner */}
          {discoveryProgress < 50 && !discoveryDismissed && (
            <div className="mx-3 mt-2 p-2 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-200 dark:border-blue-800 rounded-lg flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <div className="text-xs font-medium text-blue-700 dark:text-blue-300 whitespace-nowrap">
                  Brain: {discoveryProgress}%
                </div>
                <div className="flex-1 h-1.5 bg-blue-100 dark:bg-blue-900/40 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${discoveryProgress}%`,
                      backgroundColor: discoveryProgress < 25 ? '#ef4444' : '#f97316'
                    }}
                  />
                </div>
                <button
                  onClick={() => {
                    handleSend('Let\'s continue the business discovery. Ask me the next question.')
                  }}
                  className="text-[10px] font-medium text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
                >
                  Continue
                </button>
              </div>
              <button onClick={() => setDiscoveryDismissed(true)} className="text-gray-400 hover:text-gray-600 shrink-0">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Messages */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <Sparkles className="h-12 w-12 text-purple-300 dark:text-purple-700 mb-4" />
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  Ask O-Brain anything about your business
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Clients, finances, proposals, scheduling...
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div className={cn(
                  'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md',
                )}>
                  {/* Tool badges */}
                  {msg.tools && msg.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {msg.tools.map((t, i) => <ToolBadge key={i} name={t} />)}
                    </div>
                  )}
                  {/* Content — rendered as markdown */}
                  {msg.content ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_pre]:my-1 [&_code]:text-xs [&_pre]:text-xs [&_pre]:bg-gray-200 [&_pre]:dark:bg-gray-700 [&_pre]:rounded [&_pre]:p-2">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : null}
                  {/* Streaming indicator — pulsing dots before first chunk */}
                  {msg.isStreaming && !msg.content && (
                    <div className="flex items-center gap-1 py-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:0ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:300ms]" />
                    </div>
                  )}
                  {/* Blinking cursor while streaming with content */}
                  {msg.isStreaming && msg.content && (
                    <span className="inline-block w-1.5 h-4 bg-gray-400 dark:bg-gray-500 animate-pulse ml-0.5 align-text-bottom" />
                  )}
                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && <SourcesBadge sources={msg.sources} />}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Context indicator */}
          <div className="px-4 py-1.5 border-t border-gray-100 dark:border-gray-700">
            <p className="text-[11px] text-gray-400 dark:text-gray-500">
              Context: <span className="text-gray-500 dark:text-gray-400 font-medium">{contextLabel}</span>
            </p>
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-xl px-3 py-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask O-Brain..."
                disabled={isStreaming}
                className="flex-1 bg-transparent text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none disabled:opacity-50"
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isStreaming}
                className="p-1.5 text-blue-600 dark:text-blue-400 hover:text-blue-700 disabled:opacity-30 transition"
              >
                {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </>
      )}
    </aside>
  )

  return panel
}
