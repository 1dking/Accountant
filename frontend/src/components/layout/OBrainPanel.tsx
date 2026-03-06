import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router'
import { X, Send, Mic, Sparkles } from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

const PLACEHOLDER_RESPONSE =
  "O-Brain AI is coming soon in the next update. I'll be able to help you with anything about your business — ask me about your clients, finances, proposals, or anything else."

function getPageContext(pathname: string): string {
  const segments = pathname.split('/').filter(Boolean)
  if (segments.length === 0) return 'Dashboard'
  const labels: Record<string, string> = {
    contacts: 'Contacts',
    invoices: 'Invoices',
    proposals: 'Proposals',
    expenses: 'Expenses',
    cashbook: 'Cashbook',
    income: 'Income',
    reports: 'Reports',
    scheduling: 'Scheduling',
    workflows: 'Workflows',
    forms: 'Forms',
    conversations: 'Conversations',
    pipelines: 'Pipelines',
    drive: 'Drive',
    meetings: 'Meetings',
    settings: 'Settings',
    budgets: 'Budgets',
    estimates: 'Estimates',
    docs: 'Docs',
    sheets: 'Sheets',
    slides: 'Slides',
  }
  const page = labels[segments[0]] || segments[0].charAt(0).toUpperCase() + segments[0].slice(1)
  if (segments.length > 1) {
    return `${page} > ${segments[1].slice(0, 8)}...`
  }
  return page
}

export default function OBrainPanel() {
  const { panelState, closePanel, isMobile } = useUiStore()
  const location = useLocation()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (panelState !== 'obrain') return null

  const handleSend = () => {
    if (!input.trim()) return
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    // Simulate response after a short delay
    setTimeout(() => {
      const botMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: PLACEHOLDER_RESPONSE,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, botMsg])
    }, 500)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const contextLabel = getPageContext(location.pathname)

  const panel = (
    <aside className={cn(
      'bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 flex flex-col',
      isMobile ? 'fixed inset-0 z-50 w-full' : 'w-[340px] min-h-screen'
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">O-Brain</h2>
        </div>
        <button
          onClick={closePanel}
          className="p-1 rounded-lg text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

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
          <div
            key={msg.id}
            className={cn(
              'flex',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-md'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md'
              )}
            >
              {msg.content}
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
            className="flex-1 bg-transparent text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
          />
          <button
            onClick={() => {}}
            className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition"
            title="Voice input (coming soon)"
          >
            <Mic className="h-4 w-4" />
          </button>
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="p-1.5 text-blue-600 dark:text-blue-400 hover:text-blue-700 disabled:opacity-30 transition"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )

  return panel
}
