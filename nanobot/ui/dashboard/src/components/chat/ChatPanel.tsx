import { useState, useCallback } from 'react'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { ConversationList } from './ConversationList'
import { ChatDetailPanel } from './ChatDetailPanel'
import { ModelSelector } from './ModelSelector'
import { ThinkingToggle } from './ThinkingToggle'
import { ContextMeter } from './ContextMeter'
import { useWebSocket, useWebSocketEvent } from '@/hooks/useWebSocket'
import { useUIStore } from '@/stores/uiStore'
import { useSystem, useChatAvailability } from '@/contexts/SystemContext'
import type { Message } from '@/types'
import { generateId } from '@/lib/utils'
import { Settings, AlertCircle, Loader2, RefreshCw } from 'lucide-react'

/**
 * Setup prompt shown when chat is not available.
 */
function SetupPrompt({ 
  title, 
  description, 
  onNavigateToSettings 
}: { 
  title: string
  description: string
  onNavigateToSettings?: () => void
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="w-16 h-16 rounded-full bg-giga-accent/20 flex items-center justify-center mx-auto mb-6">
          <Settings className="w-8 h-8 text-giga-accent" />
        </div>
        <h2 className="text-xl font-semibold text-white mb-3">{title}</h2>
        <p className="text-gray-400 mb-6">{description}</p>
        {onNavigateToSettings && (
          <button
            onClick={onNavigateToSettings}
            className="px-6 py-3 bg-giga-accent text-white rounded-lg font-medium hover:bg-giga-accent/90 transition-colors"
          >
            Go to Settings
          </button>
        )}
      </div>
    </div>
  )
}

/**
 * Loading state shown during initialization.
 */
function LoadingState({ message }: { message: string }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-giga-accent animate-spin mx-auto mb-4" />
        <p className="text-gray-400">{message}</p>
      </div>
    </div>
  )
}

/**
 * Error state with retry option.
 */
function ErrorState({ 
  error, 
  onRetry 
}: { 
  error: string | null
  onRetry: () => void 
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>
        <h2 className="text-xl font-semibold text-white mb-3">Agent Error</h2>
        <p className="text-gray-400 mb-6">{error || 'An unknown error occurred'}</p>
        <button
          onClick={onRetry}
          className="px-6 py-3 bg-giga-accent text-white rounded-lg font-medium hover:bg-giga-accent/90 transition-colors inline-flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    </div>
  )
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [currentSessionId] = useState('webui:default')
  const [selectedModel, setSelectedModel] = useState('google/gemini-3-flash-preview')
  const [thinkingLevel, setThinkingLevel] = useState<'low' | 'medium' | 'high'>('medium')
  const [contextUsed, setContextUsed] = useState(2450) // Mock value - TODO: Replace with real tracking
  const [contextMax] = useState(8000) // Mock value - TODO: Get from model config
  const { send } = useWebSocket()
  const { activeChatId, setActiveChatId, userMode } = useUIStore()
  const isAdvanced = userMode === 'advanced'
  
  // System state for gating
  const { agentState, error, reinitialize, model: systemModel } = useSystem()
  const { available: chatAvailable, reason: chatUnavailableReason } = useChatAvailability()
  
  // Use system model if available
  const currentModel = systemModel || selectedModel

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

    // Send via WebSocket with model and thinking level
    send({
      action: 'chat',
      message: content,
      session_id: currentSessionId,
      model: selectedModel,
      thinking_level: thinkingLevel,
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

  const handleRetry = useCallback(async () => {
    await reinitialize()
  }, [reinitialize])

  // Gate: Show setup prompt if no API key
  if (!chatAvailable && agentState === 'uninitialized') {
    return (
      <div className="flex h-full">
        <SetupPrompt
          title="Chat Unavailable"
          description={chatUnavailableReason || "Configure an API key to enable chat."}
        />
      </div>
    )
  }

  // Gate: Show loading state during initialization
  if (agentState === 'initializing') {
    return (
      <div className="flex h-full">
        <LoadingState message="Initializing agent..." />
      </div>
    )
  }

  // Gate: Show error state with retry
  if (agentState === 'error') {
    return (
      <div className="flex h-full">
        <ErrorState error={error} onRetry={handleRetry} />
      </div>
    )
  }

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
