import { Activity, CheckCircle, AlertTriangle, Clock, Filter, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock data - TODO: Replace with real API
const mockActivities = [
  {
    id: '1',
    type: 'completion' as const,
    title: 'Research task completed',
    description: 'Gathered information about TypeScript best practices',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    status: 'success' as const,
  },
  {
    id: '2',
    type: 'scheduled' as const,
    title: 'Daily summary scheduled',
    description: 'Scheduled to run at 9:00 AM',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    status: 'pending' as const,
  },
  {
    id: '3',
    type: 'error' as const,
    title: 'API connection failed',
    description: 'Unable to reach external service - retrying...',
    timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    status: 'error' as const,
  },
  {
    id: '4',
    type: 'completion' as const,
    title: 'Message sent to Telegram',
    description: 'Successfully delivered notification to channel',
    timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    status: 'success' as const,
  },
]

type ActivityType = 'all' | 'completion' | 'scheduled' | 'error'

interface ActivityItem {
  id: string
  type: 'completion' | 'scheduled' | 'error'
  title: string
  description: string
  timestamp: string
  status: 'success' | 'pending' | 'error'
}

function ActivityCard({ activity }: { activity: ActivityItem }) {
  const getIcon = () => {
    switch (activity.status) {
      case 'success':
        return <CheckCircle size={18} className="text-giga-success" />
      case 'error':
        return <AlertTriangle size={18} className="text-giga-error" />
      case 'pending':
        return <Clock size={18} className="text-giga-warning" />
    }
  }

  const getTimeAgo = (timestamp: string) => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  return (
    <div className="card p-4 hover:bg-giga-hover transition-colors">
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{getIcon()}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-medium text-white truncate">{activity.title}</h4>
            <span className="text-xs text-gray-500 flex-shrink-0">
              {getTimeAgo(activity.timestamp)}
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">{activity.description}</p>
        </div>
      </div>
    </div>
  )
}

function ActivityFilters({ 
  selected, 
  onChange 
}: { 
  selected: ActivityType
  onChange: (type: ActivityType) => void 
}) {
  const filters: { id: ActivityType; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'completion', label: 'Completions' },
    { id: 'scheduled', label: 'Scheduled' },
    { id: 'error', label: 'Errors' },
  ]

  return (
    <div className="flex items-center gap-2">
      {filters.map((filter) => (
        <button
          key={filter.id}
          onClick={() => onChange(filter.id)}
          className={cn(
            'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            selected === filter.id
              ? 'bg-giga-accent text-white'
              : 'text-gray-400 hover:text-white hover:bg-giga-hover'
          )}
        >
          {filter.label}
        </button>
      ))}
    </div>
  )
}

export function ActivityPanel() {
  const [filter, setFilter] = useState<ActivityType>('all')

  const filteredActivities = mockActivities.filter(
    activity => filter === 'all' || activity.type === filter
  )

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-giga-accent/20 flex items-center justify-center">
              <Activity size={20} className="text-giga-accent" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Activity</h2>
              <p className="text-sm text-gray-400">Recent tasks and notifications</p>
            </div>
          </div>
          <button className="btn-secondary flex items-center gap-2">
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center justify-between gap-4">
          <ActivityFilters selected={filter} onChange={setFilter} />
          <button className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors">
            <Filter size={18} />
          </button>
        </div>

        {/* Activity List */}
        <div className="space-y-3">
          {filteredActivities.length > 0 ? (
            filteredActivities.map((activity) => (
              <ActivityCard key={activity.id} activity={activity} />
            ))
          ) : (
            <div className="card p-8 text-center">
              <Activity size={48} className="mx-auto text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-300 mb-2">No activity</h3>
              <p className="text-sm text-gray-500">
                {filter === 'all' 
                  ? 'No recent activity to display' 
                  : `No ${filter} activities found`}
              </p>
            </div>
          )}
        </div>

        {/* Upcoming Section */}
        <div className="card p-4">
          <h3 className="font-medium text-white mb-4 flex items-center gap-2">
            <Clock size={16} className="text-giga-accent" />
            Upcoming Tasks
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 rounded-lg bg-giga-dark">
              <span className="text-sm text-gray-300">Daily summary report</span>
              <span className="text-xs text-gray-500">Tomorrow, 9:00 AM</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-giga-dark">
              <span className="text-sm text-gray-300">Weekly backup</span>
              <span className="text-xs text-gray-500">Sunday, 2:00 AM</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
