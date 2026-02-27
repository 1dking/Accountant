type EventHandler = (event: WebSocketEvent) => void

export interface WebSocketEvent {
  type: string
  data: Record<string, unknown>
  timestamp: string
}

class WebSocketClient {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<EventHandler>> = new Map()
  private globalHandlers: Set<EventHandler> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private isIntentionallyClosed = false

  connect() {
    const token = localStorage.getItem('access_token')
    if (!token) return

    this.isIntentionallyClosed = false
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.reconnectDelay = 1000
      }

      this.ws.onmessage = (event) => {
        try {
          const parsed: WebSocketEvent = JSON.parse(event.data)
          this.dispatch(parsed)
        } catch {
          // Ignore malformed messages
        }
      }

      this.ws.onclose = () => {
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    } catch {
      this.scheduleReconnect()
    }
  }

  disconnect() {
    this.isIntentionallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      this.connect()
    }, this.reconnectDelay)
  }

  private dispatch(event: WebSocketEvent) {
    // Notify type-specific handlers
    const typeHandlers = this.handlers.get(event.type)
    if (typeHandlers) {
      typeHandlers.forEach((handler) => handler(event))
    }

    // Notify global handlers
    this.globalHandlers.forEach((handler) => handler(event))
  }

  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    this.handlers.get(eventType)!.add(handler)

    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler)
    }
  }

  onAny(handler: EventHandler): () => void {
    this.globalHandlers.add(handler)
    return () => {
      this.globalHandlers.delete(handler)
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const wsClient = new WebSocketClient()
