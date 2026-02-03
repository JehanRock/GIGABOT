import { 
  X, 
  MessageSquare, 
  Clock, 
  Zap, 
  Trash2,
  Download,
  RefreshCw
} from 'lucide-react'
import { useSession } from '@/hooks/useSessions'
import { formatRelativeTime, getChannelColor, getChannelInitials } from '@/lib/utils'

interface SessionDetailProps {
  sessionKey: string
  onClose: () => void
}

export function SessionDetail({ sessionKey, onClose }: SessionDetailProps) {
  const { data: session, isLoading, refetch } = useSession(sessionKey)

  const channel = sessionKey.split(':')[0] || 'web'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
        <h3 className="font-semibold text-white">Session Details</h3>
        <button 
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {isLoading ? (
          <div className="text-center text-gray-500 py-8">Loading...</div>
        ) : (
          <>
            {/* Session Info */}
            <div className="flex items-center gap-4">
              <div 
                className="w-14 h-14 rounded-xl flex items-center justify-center text-white text-lg font-bold"
                style={{ backgroundColor: getChannelColor(channel) }}
              >
                {getChannelInitials(channel)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-white truncate">{sessionKey}</p>
                <p className="text-sm text-gray-500 capitalize">{channel} channel</p>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-giga-card rounded-lg border border-sidebar-border">
                <div className="flex items-center gap-2 text-gray-400 mb-1">
                  <MessageSquare size={14} />
                  <span className="text-xs">Messages</span>
                </div>
                <p className="text-lg font-semibold text-white">
                  {session?.message_count || 0}
                </p>
              </div>
              
              <div className="p-3 bg-giga-card rounded-lg border border-sidebar-border">
                <div className="flex items-center gap-2 text-gray-400 mb-1">
                  <Clock size={14} />
                  <span className="text-xs">Last Active</span>
                </div>
                <p className="text-sm font-medium text-white">
                  {session?.last_updated 
                    ? formatRelativeTime(session.last_updated)
                    : 'N/A'
                  }
                </p>
              </div>
            </div>

            {/* Token Usage */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Token Usage
              </h4>
              <div className="p-3 bg-giga-card rounded-lg border border-sidebar-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Total Tokens</span>
                  <span className="text-sm font-medium text-white">--</span>
                </div>
                <div className="h-2 bg-giga-darker rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-giga-accent to-purple-500 rounded-full"
                    style={{ width: '60%' }}
                  />
                </div>
                <p className="text-xs text-gray-600 mt-1">
                  Context usage
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Actions
              </h4>
              
              <button 
                onClick={() => refetch()}
                className="w-full flex items-center gap-3 px-4 py-3 bg-giga-card rounded-lg border border-sidebar-border text-gray-300 hover:text-white hover:border-giga-accent transition-colors"
              >
                <RefreshCw size={18} />
                <span className="text-sm font-medium">Refresh Session</span>
              </button>
              
              <button className="w-full flex items-center gap-3 px-4 py-3 bg-giga-card rounded-lg border border-sidebar-border text-gray-300 hover:text-white hover:border-giga-accent transition-colors">
                <Zap size={18} />
                <span className="text-sm font-medium">Compact Context</span>
              </button>
              
              <button className="w-full flex items-center gap-3 px-4 py-3 bg-giga-card rounded-lg border border-sidebar-border text-gray-300 hover:text-white hover:border-giga-accent transition-colors">
                <Download size={18} />
                <span className="text-sm font-medium">Export History</span>
              </button>
              
              <button className="w-full flex items-center gap-3 px-4 py-3 bg-giga-error/10 rounded-lg border border-giga-error/20 text-giga-error hover:bg-giga-error/20 transition-colors">
                <Trash2 size={18} />
                <span className="text-sm font-medium">Delete Session</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
