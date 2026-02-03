import { 
  MessageSquare, 
  Zap, 
  AlertTriangle,
  CheckCircle,
  Clock
} from 'lucide-react'
import { cn, formatRelativeTime } from '@/lib/utils'

type ActivityType = 'message' | 'tool' | 'warning' | 'success'

interface Activity {
  id: string
  type: ActivityType
  title: string
  description: string
  timestamp: string
}

// Mock data - in production this would come from the API
const mockActivities: Activity[] = [
  {
    id: '1',
    type: 'message',
    title: 'New conversation started',
    description: 'User initiated chat from Telegram',
    timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
  {
    id: '2',
    type: 'tool',
    title: 'Tool execution completed',
    description: 'exec: npm install completed successfully',
    timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },
  {
    id: '3',
    type: 'success',
    title: 'Channel connected',
    description: 'Discord bot is now online',
    timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  },
  {
    id: '4',
    type: 'warning',
    title: 'Rate limit approaching',
    description: 'API calls nearing quota limit',
    timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
  },
  {
    id: '5',
    type: 'message',
    title: 'Session compacted',
    description: 'Reduced context from 45K to 12K tokens',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
]

function getActivityIcon(type: ActivityType) {
  switch (type) {
    case 'message':
      return <MessageSquare size={16} />
    case 'tool':
      return <Zap size={16} />
    case 'warning':
      return <AlertTriangle size={16} />
    case 'success':
      return <CheckCircle size={16} />
  }
}

function getActivityColor(type: ActivityType) {
  switch (type) {
    case 'message':
      return 'bg-giga-accent/10 text-giga-accent'
    case 'tool':
      return 'bg-purple-400/10 text-purple-400'
    case 'warning':
      return 'bg-giga-warning/10 text-giga-warning'
    case 'success':
      return 'bg-giga-success/10 text-giga-success'
  }
}

export function RecentActivity() {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-white">Recent Activity</h3>
          <p className="text-xs text-gray-500 mt-0.5">Latest system events</p>
        </div>
        
        <button className="text-xs text-giga-accent hover:text-giga-accent-hover transition-colors">
          View all
        </button>
      </div>

      {/* Activity List */}
      <div className="space-y-3">
        {mockActivities.map((activity) => (
          <div 
            key={activity.id}
            className="flex items-start gap-3 p-3 rounded-lg bg-giga-darker/50 hover:bg-giga-darker transition-colors"
          >
            {/* Icon */}
            <div className={cn(
              'p-2 rounded-lg flex-shrink-0',
              getActivityColor(activity.type)
            )}>
              {getActivityIcon(activity.type)}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {activity.title}
              </p>
              <p className="text-xs text-gray-500 truncate">
                {activity.description}
              </p>
            </div>

            {/* Timestamp */}
            <div className="flex items-center gap-1 text-xs text-gray-600 flex-shrink-0">
              <Clock size={12} />
              {formatRelativeTime(activity.timestamp)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
