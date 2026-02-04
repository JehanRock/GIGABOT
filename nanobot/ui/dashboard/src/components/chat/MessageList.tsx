import { useEffect, useRef } from 'react'
import { Bot, User, AlertCircle } from 'lucide-react'
import { ToolOutputCard } from './ToolOutputCard'
import type { Message } from '@/types'
import { cn, formatTime } from '@/lib/utils'

interface MessageListProps {
  messages: Message[]
  isTyping?: boolean
}

export function MessageList({ messages, isTyping }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  if (messages.length === 0 && !isTyping) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-giga-accent/10 flex items-center justify-center mb-4">
          <Bot size={32} className="text-giga-accent" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">
          Start a conversation
        </h3>
        <p className="text-sm text-gray-500 max-w-sm">
          Send a message to GigaBot to begin. You can ask questions, request tasks, 
          or just chat.
        </p>
      </div>
    )
  }

  return (
    <div 
      ref={containerRef}
      className="flex-1 overflow-y-auto p-4 space-y-4"
    >
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {/* Typing Indicator */}
      {isTyping && (
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-giga-card flex items-center justify-center flex-shrink-0">
            <Bot size={16} className="text-giga-accent" />
          </div>
          <div className="message-bubble-bot">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}

interface MessageBubbleProps {
  message: Message
}

function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isError = message.status === 'error'

  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className={cn(
          'px-4 py-2 rounded-lg text-sm max-w-md text-center',
          isError 
            ? 'bg-giga-error/20 text-giga-error' 
            : 'bg-giga-card text-gray-400'
        )}>
          {isError && <AlertCircle size={14} className="inline mr-2" />}
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className={cn(
      'flex items-start gap-3 w-full',
      isUser && 'flex-row-reverse'
    )}>
      {/* Avatar */}
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
        isUser 
          ? 'bg-giga-accent' 
          : 'bg-giga-card'
      )}>
        {isUser ? (
          <User size={16} className="text-white" />
        ) : (
          <Bot size={16} className="text-giga-accent" />
        )}
      </div>

      {/* Message Content */}
      <div className={cn(
        'flex flex-col gap-1',
        isUser ? 'items-end' : 'items-start'
      )}>
        <div className={cn(
          isUser ? 'message-bubble-user' : 'message-bubble-bot'
        )}>
          <p className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>

        {/* Tool Calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="space-y-2 mt-2 w-full max-w-[80%]">
            {message.toolCalls.map((toolCall) => (
              <ToolOutputCard key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-gray-500 px-1">
          {formatTime(message.timestamp)}
          {message.status === 'sending' && ' • Sending...'}
        </span>
      </div>
    </div>
  )
}
