import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X, Send, Sparkles, Loader2, MessageSquare, Plus, Trash2,
  AlertCircle, ChevronLeft, Database,
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
  type Conversation,
  type BrainAlert,
} from '@/api/brain'

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools?: string[]
  sources?: Array<{ tool: string; count: number }>
  isStreaming?: boolean
}

type PanelView = 'chat' | 'history' | 'alerts'

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
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [view, setView] = useState<PanelView>('chat')
  const messagesEndRef = useRef<HTMLDivElement>(null)

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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (panelState !== 'obrain') return null

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return
    const userText = input.trim()
    setInput('')

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

    try {
      const context = getPageContext(location.pathname)
      for await (const event of chatStream(userText, conversationId, context)) {
        if (event.type === 'text' && event.content) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') {
              last.content += event.content!
            }
            return [...updated]
          })
        } else if (event.type === 'tool_use' && event.tool) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') {
              last.tools = [...(last.tools || []), event.tool!]
            }
            return [...updated]
          })
        } else if (event.type === 'sources' && event.sources) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') {
              last.sources = event.sources
            }
            return [...updated]
          })
        } else if (event.type === 'done') {
          if (event.conversation_id) {
            setConversationId(event.conversation_id)
          }
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last.role === 'assistant') {
              last.isStreaming = false
            }
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
            {view === 'history' ? 'Conversations' : view === 'alerts' ? 'Alerts' : 'O-Brain'}
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
                onClick={() => setView('history')}
                className="p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                title="Conversation history"
              >
                <MessageSquare className="h-4 w-4" />
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

      {/* Chat View */}
      {view === 'chat' && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
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
                  {/* Content */}
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  {/* Streaming indicator */}
                  {msg.isStreaming && !msg.content && (
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
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
                onClick={handleSend}
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
