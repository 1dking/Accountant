import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, MessageSquare, Search, RefreshCw, Send, Inbox } from 'lucide-react'
import { toast } from 'sonner'
import {
  listThreads,
  getThreadMessages,
  replyToThread,
  markThreadRead,
  getUnreadCount,
  syncMessages,
} from '@/api/inbox'
import type { ThreadItem } from '@/api/inbox'
import type { UnifiedMessage } from '@/types/models'

type FilterType = 'all' | 'email' | 'sms'

function timeAgo(dateStr: string): string {
  const now = Date.now()
  const date = new Date(dateStr).getTime()
  const diff = now - date
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

export default function InboxPage() {
  const queryClient = useQueryClient()
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')
  const [replyText, setReplyText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch threads
  const threadsQuery = useQuery({
    queryKey: ['inbox', 'threads'],
    queryFn: () => listThreads(1, 100),
    refetchInterval: 30000,
  })

  // Fetch unread count
  const unreadQuery = useQuery({
    queryKey: ['inbox', 'unread-count'],
    queryFn: getUnreadCount,
    refetchInterval: 30000,
  })

  // Fetch thread messages when a thread is selected
  const threadMessagesQuery = useQuery({
    queryKey: ['inbox', 'thread-messages', selectedThreadId],
    queryFn: () => getThreadMessages(selectedThreadId!),
    enabled: !!selectedThreadId,
  })

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: syncMessages,
    onSuccess: (res) => {
      toast.success(res.data.message)
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
    onError: () => {
      toast.error('Failed to sync messages')
    },
  })

  // Reply mutation
  const replyMutation = useMutation({
    mutationFn: (params: { threadId: string; body: string }) =>
      replyToThread(params.threadId, params.body),
    onSuccess: () => {
      setReplyText('')
      queryClient.invalidateQueries({ queryKey: ['inbox', 'thread-messages', selectedThreadId] })
      queryClient.invalidateQueries({ queryKey: ['inbox', 'threads'] })
      toast.success('Reply sent')
    },
    onError: () => {
      toast.error('Failed to send reply')
    },
  })

  // Mark thread as read mutation
  const markReadMutation = useMutation({
    mutationFn: markThreadRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox', 'threads'] })
      queryClient.invalidateQueries({ queryKey: ['inbox', 'unread-count'] })
    },
  })

  // Auto-mark thread as read when selected
  useEffect(() => {
    if (selectedThreadId) {
      const threads = threadsQuery.data?.data ?? []
      const thread = threads.find((t) => t.message.thread_id === selectedThreadId)
      if (thread && thread.unread_count > 0) {
        markReadMutation.mutate(selectedThreadId)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedThreadId])

  // Scroll to bottom when messages load
  useEffect(() => {
    if (threadMessagesQuery.data) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [threadMessagesQuery.data])

  // Filter and search threads
  const threads: ThreadItem[] = (threadsQuery.data?.data ?? []).filter((t) => {
    // Filter by type
    if (filter === 'email' && !t.message.thread_id?.startsWith('email:')) return false
    if (filter === 'sms' && !t.message.thread_id?.startsWith('sms:')) return false

    // Filter by search
    if (search.trim()) {
      const q = search.toLowerCase()
      const subject = (t.message.subject ?? '').toLowerCase()
      const body = (t.message.body ?? '').toLowerCase()
      const recipient = (t.message.recipient ?? '').toLowerCase()
      const sender = (t.message.sender ?? '').toLowerCase()
      if (!subject.includes(q) && !body.includes(q) && !recipient.includes(q) && !sender.includes(q)) {
        return false
      }
    }

    return true
  })

  const messages: UnifiedMessage[] = threadMessagesQuery.data?.data ?? []
  const selectedThread = threads.find((t) => t.message.thread_id === selectedThreadId)

  const unreadCount = unreadQuery.data?.data

  function handleSelectThread(threadId: string) {
    setSelectedThreadId(threadId)
    setReplyText('')
  }

  function handleSendReply() {
    if (!selectedThreadId || !replyText.trim()) return
    replyMutation.mutate({ threadId: selectedThreadId, body: replyText.trim() })
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Panel - Thread List */}
      <div className="w-96 flex-shrink-0 flex flex-col border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        {/* Top bar */}
        <div className="p-4 border-b border-gray-100 dark:border-gray-700 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Inbox</h1>
              {unreadCount && unreadCount.total > 0 && (
                <span className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 text-xs font-medium px-2 py-0.5 rounded-full">
                  {unreadCount.total}
                </span>
              )}
            </div>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
              title="Sync messages"
            >
              <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Filter pills */}
          <div className="flex gap-2">
            {(['all', 'email', 'sms'] as FilterType[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded-full text-sm transition-colors ${
                  filter === f
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800'
                }`}
              >
                {f === 'all' ? 'All' : f === 'email' ? 'Email' : 'SMS'}
                {f === 'email' && unreadCount && unreadCount.email > 0 && (
                  <span className="ml-1 text-xs opacity-70">({unreadCount.email})</span>
                )}
                {f === 'sms' && unreadCount && unreadCount.sms > 0 && (
                  <span className="ml-1 text-xs opacity-70">({unreadCount.sms})</span>
                )}
              </button>
            ))}
          </div>

          {/* Search input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search messages..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Thread list */}
        <div className="flex-1 overflow-y-auto">
          {threadsQuery.isLoading ? (
            <div className="p-8 text-center text-gray-400">Loading threads...</div>
          ) : threads.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <Inbox className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No messages found</p>
            </div>
          ) : (
            threads.map((thread) => {
              const msg = thread.message
              const threadId = msg.thread_id ?? msg.id
              const isSelected = selectedThreadId === threadId
              const isUnread = thread.unread_count > 0
              const isEmail = msg.message_type === 'email'

              return (
                <button
                  key={threadId}
                  onClick={() => handleSelectThread(threadId)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-50 dark:border-gray-800 transition-colors ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800/50 border-l-2 border-l-transparent'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Type icon */}
                    <div className="mt-0.5 flex-shrink-0">
                      {isEmail ? (
                        <Mail className="w-4 h-4 text-gray-400" />
                      ) : (
                        <MessageSquare className="w-4 h-4 text-gray-400" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p
                          className={`text-sm truncate ${
                            isUnread
                              ? 'font-semibold text-gray-900 dark:text-gray-100'
                              : 'text-gray-700 dark:text-gray-300'
                          }`}
                        >
                          {msg.subject || msg.body?.slice(0, 50) || 'No subject'}
                        </p>
                        <span className="text-xs text-gray-400 flex-shrink-0">
                          {timeAgo(msg.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {msg.direction === 'inbound' ? msg.sender : msg.recipient}
                      </p>
                      {msg.body && (
                        <p className="text-xs text-gray-400 truncate mt-0.5">
                          {msg.body.slice(0, 80)}
                        </p>
                      )}
                    </div>

                    {/* Indicators */}
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      {isUnread && <div className="w-2 h-2 rounded-full bg-blue-500" />}
                      {thread.message_count > 1 && (
                        <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded-full">
                          {thread.message_count}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Right Panel - Thread Detail */}
      <div className="flex-1 flex flex-col bg-gray-50 dark:bg-gray-950">
        {!selectedThreadId ? (
          /* Empty state */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <Mail className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-lg font-medium">Select a thread to view messages</p>
              <p className="text-sm mt-1">Choose a conversation from the left panel</p>
            </div>
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div className="px-6 py-4 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {selectedThread?.message.subject || 'Conversation'}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {selectedThread?.message.direction === 'inbound'
                  ? `From: ${selectedThread?.message.sender ?? 'Unknown'}`
                  : `To: ${selectedThread?.message.recipient ?? 'Unknown'}`}
                {selectedThread && selectedThread.message_count > 1 && (
                  <span className="ml-2">
                    ({selectedThread.message_count} message{selectedThread.message_count !== 1 ? 's' : ''})
                  </span>
                )}
              </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {threadMessagesQuery.isLoading ? (
                <div className="text-center text-gray-400 py-8">Loading messages...</div>
              ) : messages.length === 0 ? (
                <div className="text-center text-gray-400 py-8">No messages in this thread</div>
              ) : (
                messages.map((msg) => {
                  const isOutbound = msg.direction === 'outbound'
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`rounded-xl p-3 max-w-[80%] ${
                          isOutbound
                            ? 'bg-blue-50 dark:bg-blue-900/30 ml-auto'
                            : 'bg-gray-100 dark:bg-gray-800 mr-auto'
                        }`}
                      >
                        {msg.subject && (
                          <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                            {msg.subject}
                          </p>
                        )}
                        <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                          {msg.body}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-gray-400">
                            {timeAgo(msg.created_at)}
                          </span>
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${
                              isOutbound
                                ? 'bg-blue-100 text-blue-600 dark:bg-blue-800/40 dark:text-blue-300'
                                : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                            }`}
                          >
                            {isOutbound ? 'Sent' : 'Received'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Reply box */}
            <div className="px-6 py-4 bg-white dark:bg-gray-900 border-t border-gray-100 dark:border-gray-700">
              <div className="flex gap-3">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type your reply..."
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                      handleSendReply()
                    }
                  }}
                  className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
                <button
                  onClick={handleSendReply}
                  disabled={!replyText.trim() || replyMutation.isPending}
                  className="self-end px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  <Send className="w-4 h-4" />
                  {replyMutation.isPending ? 'Sending...' : 'Send'}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">Press Ctrl+Enter to send</p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
