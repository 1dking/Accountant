import { api } from './client'

// ── Chat (SSE streaming) ──────────────────────────────────────────────

export interface ChatStreamEvent {
  type: 'text' | 'tool_use' | 'sources' | 'done' | 'error'
  content?: string
  tool?: string
  sources?: Array<{ tool: string; count: number }>
  conversation_id?: string
  message_id?: string
}

export async function* chatStream(
  message: string,
  conversationId?: string | null,
  pageContext?: string,
  fileIds?: string[],
): AsyncGenerator<ChatStreamEvent> {
  const token = localStorage.getItem('access_token')
  const resp = await fetch('/api/brain/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
      page_context: pageContext || 'General',
      ...(fileIds && fileIds.length > 0 ? { file_ids: fileIds } : {}),
    }),
  })

  if (!resp.ok || !resp.body) {
    yield { type: 'error', content: 'Failed to connect to O-Brain' }
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event: ChatStreamEvent = JSON.parse(line.slice(6))
          yield event
        } catch {
          // Skip malformed events
        }
      }
    }
  }
}

// ── Conversations ─────────────────────────────────────────────────────

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[] | null
  sources?: Array<{ tool: string; count: number }> | null
  created_at: string
}

export interface ConversationDetail {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: ConversationMessage[]
}

export const listConversations = (limit = 20) =>
  api.get<{ data: Conversation[] }>(`/brain/conversations?limit=${limit}`)

export const getConversation = (id: string) =>
  api.get<{ data: ConversationDetail }>(`/brain/conversations/${id}`)

export const deleteConversation = (id: string) =>
  api.delete(`/brain/conversations/${id}`)

// ── Knowledge Base ────────────────────────────────────────────────────

export interface KnowledgeItem {
  source_id: string
  title: string
  category: string
  chunk_count: number
  created_at: string | null
}

export const addKnowledge = (content: string, title: string, category = 'general') =>
  api.post('/brain/knowledge', { content, title, category })

export const listKnowledge = (page = 1, pageSize = 20, category?: string) =>
  api.get<{ data: { items: KnowledgeItem[]; total: number } }>(
    `/brain/knowledge?page=${page}&page_size=${pageSize}${category ? `&category=${category}` : ''}`
  )

export const deleteKnowledge = (sourceId: string) =>
  api.delete(`/brain/knowledge/${sourceId}`)

export const getOnboardingQuestions = () =>
  api.get<{ data: Array<{ id: string; question: string; placeholder: string }> }>(
    '/brain/knowledge/onboarding'
  )

export const submitOnboarding = (answers: Array<{ question: string; answer: string }>) =>
  api.post('/brain/knowledge/onboarding', { answers })

// ── Search ────────────────────────────────────────────────────────────

export interface BrainSearchResult {
  content: string
  source_type: string
  source_id: string
  relevance_score: number
}

export const searchBrain = (query: string, limit = 10, sourceType?: string) =>
  api.post<{ data: BrainSearchResult[] }>('/brain/search', { query, limit, source_type: sourceType })

// ── Alerts ────────────────────────────────────────────────────────────

export interface BrainAlert {
  id: string
  alert_type: string
  title: string
  message: string
  is_read: boolean
  data: Record<string, unknown> | null
  created_at: string
}

export const listAlerts = (unreadOnly = false, limit = 20) =>
  api.get<{ data: BrainAlert[] }>(`/brain/alerts?unread_only=${unreadOnly}&limit=${limit}`)

export const markAlertRead = (alertId: string) =>
  api.post(`/brain/alerts/${alertId}/read`)

export const markAllAlertsRead = () =>
  api.post('/brain/alerts/read-all')

export const getDailyBriefing = () =>
  api.get<{ data: { date: string; alert_count: number; alerts: BrainAlert[] } }>('/brain/briefing')

export const generateBriefing = () =>
  api.post('/brain/briefing/generate')

// ── Transcription ─────────────────────────────────────────────────────

export const transcribeMeeting = (meetingId: string, file: File, language = 'en') => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('language', language)
  return api.upload(`/brain/transcribe/meeting/${meetingId}`, fd)
}

export const transcribeCall = (callSid: string, file: File, contactId?: string, language = 'en') => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('call_sid', callSid)
  if (contactId) fd.append('contact_id', contactId)
  fd.append('language', language)
  return api.upload('/brain/transcribe/call', fd)
}

export const importTranscript = (text: string, sourceType = 'meeting', meetingId?: string, callSid?: string, contactId?: string) =>
  api.post('/brain/transcribe/import', { text, source_type: sourceType, meeting_id: meetingId, call_sid: callSid, contact_id: contactId })

// ── Discovery ────────────────────────────────────────────────────────

export const getDiscoveryQuestions = () =>
  api.get<{ data: Array<{ section: string; questions: Array<{ id: string; question: string; placeholder: string; order: number }> }> }>(
    '/brain/discovery/questions'
  )

export const submitDiscoveryAnswers = (answers: Array<{ id: string; question: string; answer: string }>) =>
  api.post<{ data: { saved_count: number; total: number } }>('/brain/discovery/submit', { answers })

// ── Audit ─────────────────────────────────────────────────────────────

export const listAuditLogs = (limit = 50) =>
  api.get<{ data: Array<{ id: string; action_type: string; ai_input: string | null; ai_output: string | null; created_at: string }> }>(
    `/brain/audit?limit=${limit}`
  )
