import { createContext, useContext, useEffect, useRef, useCallback, useState, ReactNode } from 'react'
import { useUIStore } from '@/stores/uiStore'
import type { WebSocketEvent, WebSocketAction } from '@/types'

interface WebSocketContextValue {
  send: (action: WebSocketAction) => void
  subscribe: (callback: (event: WebSocketEvent) => void) => () => void
  isConnected: boolean
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

interface WebSocketProviderProps {
  children: ReactNode
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const reconnectAttemptsRef = useRef(0)
  const subscribersRef = useRef<Set<(event: WebSocketEvent) => void>>(new Set())
  const [isConnected, setIsConnected] = useState(false)
  
  const { setConnectionStatus, authToken } = useUIStore()

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    
    // In development, use the proxy
    if (import.meta.env.DEV) {
      return `${protocol}//${host}/ws`
    }
    
    return `${protocol}//${host}/ws`
  }, [])

  const broadcast = useCallback((event: WebSocketEvent) => {
    subscribersRef.current.forEach(callback => {
      try {
        callback(event)
      } catch (error) {
        console.error('WebSocket subscriber error:', error)
      }
    })
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setConnectionStatus('connecting')

    try {
      const url = new URL(getWebSocketUrl())
      
      // Add auth token if available
      if (authToken) {
        url.searchParams.set('token', authToken)
      }

      const ws = new WebSocket(url.toString())
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnectionStatus('connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        broadcast({ type: 'connected' })
        
        // Start ping interval
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }))
          }
        }, 30000)
        
        ws.addEventListener('close', () => clearInterval(pingInterval))
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketEvent
          broadcast(data)
        } catch (error) {
          console.error('WebSocket message parse error:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        setConnectionStatus('disconnected')
        setIsConnected(false)
        wsRef.current = null
        broadcast({ type: 'disconnected' })

        // Reconnect with exponential backoff
        const maxDelay = 30000
        const baseDelay = 1000
        const delay = Math.min(
          maxDelay,
          baseDelay * Math.pow(2, reconnectAttemptsRef.current)
        )
        
        reconnectAttemptsRef.current++
        
        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`)
        reconnectTimeoutRef.current = setTimeout(connect, delay)
      }
    } catch (error) {
      console.error('WebSocket connection error:', error)
      setConnectionStatus('disconnected')
    }
  }, [getWebSocketUrl, authToken, setConnectionStatus, broadcast])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect')
      wsRef.current = null
    }
  }, [])

  const send = useCallback((action: WebSocketAction) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(action))
    } else {
      console.warn('WebSocket not connected, cannot send:', action)
    }
  }, [])

  const subscribe = useCallback((callback: (event: WebSocketEvent) => void) => {
    subscribersRef.current.add(callback)
    return () => {
      subscribersRef.current.delete(callback)
    }
  }, [])

  // Connect on mount
  useEffect(() => {
    connect()
    return disconnect
  }, [connect, disconnect])

  const value: WebSocketContextValue = {
    send,
    subscribe,
    isConnected,
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

// Hook for subscribing to specific event types
export function useWebSocketEvent<T extends WebSocketEvent['type']>(
  type: T,
  callback: (event: Extract<WebSocketEvent, { type: T }>) => void
) {
  const { subscribe } = useWebSocket()

  useEffect(() => {
    return subscribe((event) => {
      if (event.type === type) {
        callback(event as Extract<WebSocketEvent, { type: T }>)
      }
    })
  }, [subscribe, type, callback])
}
