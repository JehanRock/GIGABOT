import { useState } from 'react'
import { Search, Filter, MessageSquare } from 'lucide-react'
import { useSessions } from '@/hooks/useSessions'
import { cn, formatRelativeTime, getChannelColor, getChannelInitials } from '@/lib/utils'

interface ConversationListProps {
  activeId: string | null
  onSelect: (id: string | null) => void
}

type FilterType = 'all' | 'open' | 'unread'

export function ConversationList({ activeId, onSelect }: ConversationListProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filter, setFilter] = useState<FilterType>('all')
  const { data, isLoading } = useSessions()

  const sessions = data?.sessions || []

  // Filter sessions
  const filteredSessions = sessions.filter(session => {
    if (searchQuery) {
      return session.key.toLowerCase().includes(searchQuery.toLowerCase())
    }
    return true
  })

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <h2 className="font-semibold text-white mb-3">Conversations</h2>
        
        {/* Search */}
        <div className="relative mb-3">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-giga-card border border-sidebar-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-giga-accent transition-colors"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          {(['all', 'open', 'unread'] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-full transition-colors',
                filter === f
                  ? 'bg-giga-accent text-white'
                  : 'bg-giga-card text-gray-400 hover:text-white'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500">
            Loading...
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="p-8 text-center">
            <MessageSquare size={32} className="mx-auto text-gray-600 mb-2" />
            <p className="text-sm text-gray-500">No conversations yet</p>
          </div>
        ) : (
          filteredSessions.map((session) => (
            <ConversationItem
              key={session.key}
              session={session}
              isActive={activeId === session.key}
              onClick={() => onSelect(session.key)}
            />
          ))
        )}
      </div>
    </div>
  )
}

interface ConversationItemProps {
  session: {
    key: string
    message_count: number
    last_updated?: string
    channel?: string
  }
  isActive: boolean
  onClick: () => void
}

function ConversationItem({ session, isActive, onClick }: ConversationItemProps) {
  // Extract channel from session key (e.g., "telegram:123" -> "telegram")
  const channel = session.channel || session.key.split(':')[0] || 'web'
  const channelColor = getChannelColor(channel)
  const channelInitials = getChannelInitials(channel)

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-3 p-3 border-b border-sidebar-border transition-colors text-left',
        'hover:bg-giga-hover',
        isActive && 'bg-giga-hover'
      )}
    >
      {/* Avatar with channel badge */}
      <div className="relative flex-shrink-0">
        <div 
          className="w-10 h-10 rounded-full flex items-center justify-center text-white text-xs font-bold"
          style={{ backgroundColor: channelColor }}
        >
          {channelInitials}
        </div>
        {/* Online indicator */}
        <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-giga-success border-2 border-giga-dark" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-0.5">
          <span className="font-medium text-white text-sm truncate">
            {session.key}
          </span>
          {session.last_updated && (
            <span className="text-[10px] text-gray-500 flex-shrink-0">
              {formatRelativeTime(session.last_updated)}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500 truncate">
          {session.message_count} messages
        </p>
      </div>

      {/* Unread badge */}
      {session.message_count > 0 && (
        <div className="flex-shrink-0">
          <span className="inline-flex items-center justify-center w-5 h-5 text-[10px] font-bold rounded-full bg-giga-accent text-white">
            {session.message_count > 99 ? '99+' : session.message_count}
          </span>
        </div>
      )}
    </button>
  )
}
