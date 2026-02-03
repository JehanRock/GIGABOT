import { useState, useCallback, useEffect } from 'react'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { ConversationList } from './ConversationList'
import { ChatDetailPanel } from './ChatDetailPanel'
import { ModelSelector } from './ModelSelector'
import { ThinkingToggle } from './ThinkingToggle'
import { ContextMeter } from './ContextMeter'
import { useWebSocket, useWebSocketEvent } from '@/hooks/useWebSocket'
import { useUIStore } from '@/stores/uiStore'
import type { Message } from '@/types'
import { generateId } from '@/lib/utils'

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [currentSessionId] = useState('webui:default')
  const [selectedModel, setSelectedModel] = useState('gpt-4-turbo')
  const [thinkingLevel, setThinkingLevel] = useState<'low' | 'medium' | 'high'>('medium')
  const [contextUsed, setContextUsed] = useState(2450) // Mock value - TODO: Replace with real tracking
  const [contextMax] = useState(8000) // Mock value - TODO: Get from model config
  const { send } = useWebSocket()
  const { activeChatId, setActiveChatId, userMode } = useUIStore()
  const isAdvanced = userMode === 'advanced'

  // Handle incoming messages
  useWebSocketEvent('response', useCallback((event) => {
    const newMessage: Message = {
      id: generateId(),
      content: event.content,
      timestamp: new Date().toISOString(),
      role: 'assistant',
      status: 'sent',
    }
    setMessages(prev => [...prev, newMessage])
  }, []))

  // Handle typing indicator
  useWebSocketEvent('typing', useCallback((event) => {
    setIsTyping(event.status)
  }, []))

  // Handle errors
  useWebSocketEvent('error', useCallback((event) => {
    const errorMessage: Message = {
      id: generateId(),
      content: `Error: ${event.error}`,
      timestamp: new Date().toISOString(),
      role: 'system',
      status: 'error',
    }
    setMessages(prev => [...prev, errorMessage])
  }, []))

  const handleSendMessage = useCallback((content: string) => {
    // Add user message to list
    const userMessage: Message = {
      id: generateId(),
      content,
      timestamp: new Date().toISOString(),
      role: 'user',
      status: 'sending',
    }
    setMessages(prev => [...prev, userMessage])

    // Send via WebSocket
    send({
      action: 'chat',
      message: content,
      session_id: currentSessionId,
    })

    // Update status to sent
    setTimeout(() => {
      setMessages(prev => 
        prev.map(m => 
          m.id === userMessage.id ? { ...m, status: 'sent' } : m
        )
      )
    }, 100)
  }, [send, currentSessionId])

  const handleAbort = useCallback(() => {
    send({
      action: 'abort',
      session_id: currentSessionId,
    })
    setIsTyping(false)
  }, [send, currentSessionId])

  return (
    <div className="flex h-full">
      {/* Conversation List - Hidden on mobile, shown on tablet+ */}
      <div className="hidden lg:flex w-80 border-r border-sidebar-border flex-col">
        <ConversationList 
          activeId={activeChatId}
          onSelect={setActiveChatId}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        <div className="border-b border-sidebar-border">
          {/* Main header row */}
          <div className="h-14 flex items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-giga-accent/20 flex items-center justify-center">
                <span className="text-giga-accent text-sm font-bold">G</span>
              </div>
              <div>
                <h2 className="font-semibold text-white text-sm">GigaBot</h2>
                <p className="text-xs text-gray-500">
                  {isTyping ? 'Typing...' : 'Online'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isTyping && (
                <button
                  onClick={handleAbort}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-giga-error/20 text-giga-error hover:bg-giga-error/30 transition-colors"
                >
                  Stop
                </button>
              )}
            </div>
          </div>
          
          {/* Advanced controls row - only shown in advanced mode */}
          {isAdvanced && (
            <div className="h-10 flex items-center justify-between px-4 bg-giga-dark/50 border-t border-giga-border">
              <div className="flex items-center gap-4">
                <ModelSelector 
                  selectedModel={selectedModel}
                  onModelChange={setSelectedModel}
                />
                <ThinkingToggle 
                  level={thinkingLevel}
                  onLevelChange={setThinkingLevel}
                />
              </div>
              <ContextMeter 
                usedTokens={contextUsed}
                maxTokens={contextMax}
              />
            </div>
          )}
        </div>

        {/* Messages */}
        <MessageList 
          messages={messages} 
          isTyping={isTyping}
        />

        {/* Input */}
        <MessageInput 
          onSend={handleSendMessage}
          disabled={isTyping}
        />
      </div>

      {/* Detail Panel - Hidden on mobile/tablet, shown on desktop */}
      <div className="hidden xl:flex w-80 border-l border-sidebar-border flex-col">
        <ChatDetailPanel />
      </div>
    </div>
  )
}
