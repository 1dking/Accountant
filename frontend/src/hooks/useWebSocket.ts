import { useEffect, useState } from 'react'
import { wsClient, type WebSocketEvent } from '@/api/websocket'

/**
 * Subscribe to a specific WebSocket event type.
 * Returns the most recent event of that type.
 */
export function useWebSocket(eventType: string) {
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null)

  useEffect(() => {
    const unsubscribe = wsClient.on(eventType, (event) => {
      setLastEvent(event)
    })
    return unsubscribe
  }, [eventType])

  return { lastEvent }
}

/**
 * Subscribe to all WebSocket events.
 */
export function useWebSocketAll() {
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null)

  useEffect(() => {
    const unsubscribe = wsClient.onAny((event) => {
      setLastEvent(event)
    })
    return unsubscribe
  }, [])

  return { lastEvent }
}
