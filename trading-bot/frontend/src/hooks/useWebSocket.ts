import { useEffect, useRef, useCallback } from 'react'
import type { WSMessage } from '@/types'

export function useWebSocket(
  userId: string | null,
  onMessage: (msg: WSMessage) => void
) {
  const ws = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    if (!userId) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    ws.current = new WebSocket(`${proto}://${window.location.host}/ws/${userId}`)

    ws.current.onmessage = (e) => {
      try {
        const msg: WSMessage = JSON.parse(e.data)
        onMessage(msg)
      } catch { /* ignore malformed messages */ }
    }

    ws.current.onclose = () => {
      // Reconnect after 3 seconds on unexpected close
      setTimeout(connect, 3_000)
    }
  }, [userId, onMessage])

  useEffect(() => {
    connect()
    return () => ws.current?.close()
  }, [connect])
}
