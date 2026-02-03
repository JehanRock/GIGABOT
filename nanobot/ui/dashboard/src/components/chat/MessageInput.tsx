import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { Send, Paperclip, Smile, Mic, Command } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MessageInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export function MessageInput({ 
  onSend, 
  disabled = false,
  placeholder = 'Type a message...'
}: MessageInputProps) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`
    }
  }, [message])

  const handleSubmit = () => {
    const trimmed = message.trim()
    if (trimmed && !disabled) {
      onSend(trimmed)
      setMessage('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="border-t border-sidebar-border p-4 bg-giga-darker/50">
      <div className="flex items-end gap-2">
        {/* Attachment Button */}
        <button
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
          title="Attach file"
        >
          <Paperclip size={20} />
        </button>

        {/* Text Input */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={cn(
              'w-full px-4 py-3 pr-24 bg-giga-card border border-sidebar-border rounded-xl',
              'text-white placeholder-gray-500 text-sm',
              'focus:outline-none focus:border-giga-accent focus:ring-1 focus:ring-giga-accent',
              'transition-all duration-200 resize-none',
              'max-h-[150px] scrollbar-hide',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          />
          
          {/* Quick Actions (inside input) */}
          <div className="absolute right-2 bottom-2 flex items-center gap-1">
            <button
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 transition-colors"
              title="Emoji"
            >
              <Smile size={18} />
            </button>
            <button
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 transition-colors"
              title="Commands (type /)"
            >
              <Command size={18} />
            </button>
          </div>
        </div>

        {/* Voice Input */}
        <button
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
          title="Voice input"
        >
          <Mic size={20} />
        </button>

        {/* Send Button */}
        <button
          onClick={handleSubmit}
          disabled={disabled || !message.trim()}
          className={cn(
            'p-3 rounded-xl transition-all duration-200',
            message.trim() && !disabled
              ? 'bg-giga-accent hover:bg-giga-accent-hover text-white'
              : 'bg-giga-card text-gray-500 cursor-not-allowed'
          )}
          title="Send message"
        >
          <Send size={20} />
        </button>
      </div>

      {/* Hints */}
      <div className="flex items-center justify-between mt-2 px-1">
        <p className="text-[10px] text-gray-600">
          Press <kbd className="px-1 py-0.5 bg-giga-card rounded text-gray-500">Enter</kbd> to send, 
          <kbd className="px-1 py-0.5 bg-giga-card rounded text-gray-500 ml-1">Shift+Enter</kbd> for new line
        </p>
        <p className="text-[10px] text-gray-600">
          {message.length > 0 && `${message.length} chars`}
        </p>
      </div>
    </div>
  )
}
