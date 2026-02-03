import { CheckCircle, AlertTriangle, XCircle, Radio, Zap, Clock, DollarSign } from 'lucide-react'
import { useStatus, useTracking } from '@/hooks/useStatus'
import { useSessions } from '@/hooks/useSessions'
import { useChannels } from '@/hooks/useChannels'
import { cn, formatCurrency } from '@/lib/utils'

type SystemStatus = 'online' | 'busy' | 'offline'

function getOverallStatus(status: any): SystemStatus {
  if (!status?.gateway || status?.gateway === 'offline') return 'offline'
  if (status?.provider === 'error' || status?.provider === 'degraded') return 'busy'
  return 'online'
}

function StatusBadge({ status }: { status: SystemStatus }) {
  const config = {
    online: {
      icon: <CheckCircle size={24} />,
      label: 'Online',
      color: 'text-giga-success bg-giga-success/10 border-giga-success/30',
    },
    busy: {
      icon: <AlertTriangle size={24} />,
      label: 'Busy',
      color: 'text-giga-warning bg-giga-warning/10 border-giga-warning/30',
    },
    offline: {
      icon: <XCircle size={24} />,
      label: 'Offline',
      color: 'text-giga-error bg-giga-error/10 border-giga-error/30',
    },
  }

  const { icon, label, color } = config[status]

  return (
    <div className={cn('flex items-center gap-3 p-4 rounded-xl border', color)}>
      {icon}
      <div>
        <p className="text-lg font-bold">{label}</p>
        <p className="text-xs opacity-70">System Status</p>
      </div>
    </div>
  )
}

function ChannelStatusDots() {
  const { data: channels } = useChannels()

  // Convert channels object to array
  const channelEntries = channels?.channels 
    ? Object.entries(channels.channels).map(([name, status]) => ({ name, ...status }))
    : []
  const connectedCount = channelEntries.filter((c) => c.connected).length

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Radio size={16} className="text-giga-accent" />
        <h3 className="font-medium text-white">Channels</h3>
      </div>
      <div className="flex items-center gap-3">
        {channelEntries.length > 0 ? (
          channelEntries.map((channel) => (
            <div key={channel.name} className="flex flex-col items-center gap-1">
              <div className={cn(
                'w-3 h-3 rounded-full',
                channel.connected ? 'bg-giga-success' : 'bg-giga-error'
              )} />
              <span className="text-[10px] text-gray-500 capitalize">{channel.name}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-gray-500">No channels configured</p>
        )}
      </div>
      {channelEntries.length > 0 && (
        <p className="text-xs text-gray-500 mt-3">
          {connectedCount} of {channelEntries.length} connected
        </p>
      )}
    </div>
  )
}

function SimplifiedUsage() {
  const { data: tracking } = useTracking()

  const stats = tracking?.session || { estimated_cost: 0 }
  const usageLevel = stats.estimated_cost < 0.5 ? 'Normal' : stats.estimated_cost < 2 ? 'Moderate' : 'High'
  const usageColor = stats.estimated_cost < 0.5 ? 'text-giga-success' : stats.estimated_cost < 2 ? 'text-giga-warning' : 'text-giga-error'

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Zap size={16} className="text-giga-accent" />
        <h3 className="font-medium text-white">Usage</h3>
      </div>
      <div className="flex items-center justify-between">
        <div>
          <p className={cn('text-lg font-bold', usageColor)}>{usageLevel}</p>
          <p className="text-xs text-gray-500">Today's usage level</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold text-white">{formatCurrency(stats.estimated_cost)}</p>
          <p className="text-xs text-gray-500">Estimated cost</p>
        </div>
      </div>
    </div>
  )
}

function ActiveTasksBadge() {
  const { data: sessions } = useSessions()
  const activeCount = sessions?.sessions?.filter((s: any) => s.active)?.length || 0

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} className="text-giga-accent" />
        <h3 className="font-medium text-white">Active Tasks</h3>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-full bg-giga-dark flex items-center justify-center">
            <span className="text-2xl font-bold text-white">{activeCount}</span>
          </div>
          {activeCount > 0 && (
            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-giga-success animate-pulse" />
          )}
        </div>
        <div>
          <p className="text-sm text-gray-300">
            {activeCount === 0 ? 'No active tasks' : activeCount === 1 ? '1 task running' : `${activeCount} tasks running`}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            GigaBot is {activeCount > 0 ? 'working' : 'idle'}
          </p>
        </div>
      </div>
    </div>
  )
}

export function SimpleStatusCard() {
  const { data: status } = useStatus()
  const overallStatus = getOverallStatus(status)

  return (
    <div className="space-y-4">
      {/* Main Status */}
      <StatusBadge status={overallStatus} />

      {/* Quick Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <ChannelStatusDots />
        <SimplifiedUsage />
        <ActiveTasksBadge />
      </div>
    </div>
  )
}
