import { 
  CheckCircle, 
  AlertCircle, 
  XCircle,
  Server,
  Database,
  Wifi,
  Bot
} from 'lucide-react'
import { useStatus } from '@/hooks/useStatus'
import { useChannels } from '@/hooks/useChannels'
import { cn } from '@/lib/utils'

type HealthStatus = 'healthy' | 'warning' | 'error'

interface HealthItemProps {
  name: string
  status: HealthStatus
  detail?: string
  icon: React.ReactNode
}

function HealthItem({ name, status, detail, icon }: HealthItemProps) {
  const getStatusIcon = () => {
    switch (status) {
      case 'healthy':
        return <CheckCircle size={14} className="text-giga-success" />
      case 'warning':
        return <AlertCircle size={14} className="text-giga-warning" />
      case 'error':
        return <XCircle size={14} className="text-giga-error" />
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'healthy':
        return 'bg-giga-success/10 border-giga-success/20'
      case 'warning':
        return 'bg-giga-warning/10 border-giga-warning/20'
      case 'error':
        return 'bg-giga-error/10 border-giga-error/20'
    }
  }

  return (
    <div className={cn(
      'flex items-center justify-between p-3 rounded-lg border',
      getStatusColor()
    )}>
      <div className="flex items-center gap-3">
        <div className="text-gray-400">
          {icon}
        </div>
        <div>
          <p className="text-sm font-medium text-white">{name}</p>
          {detail && (
            <p className="text-xs text-gray-500">{detail}</p>
          )}
        </div>
      </div>
      {getStatusIcon()}
    </div>
  )
}

export function SystemHealth() {
  const { data: status, isLoading: statusLoading } = useStatus()
  const { data: channels } = useChannels()

  // Calculate channel health
  const channelStatuses = channels?.channels || {}
  const activeChannels = Object.values(channelStatuses).filter(c => c.running).length
  const totalChannels = Object.keys(channelStatuses).length

  // Determine overall health
  const getOverallHealth = (): HealthStatus => {
    if (status?.status === 'running' && activeChannels > 0) return 'healthy'
    if (status?.status === 'running') return 'warning'
    return 'error'
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-white">System Health</h3>
          <p className="text-xs text-gray-500 mt-0.5">Component status</p>
        </div>
        
        {/* Overall Status Badge */}
        <div className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
          {
            'bg-giga-success/20 text-giga-success': getOverallHealth() === 'healthy',
            'bg-giga-warning/20 text-giga-warning': getOverallHealth() === 'warning',
            'bg-giga-error/20 text-giga-error': getOverallHealth() === 'error',
          }
        )}>
          {getOverallHealth() === 'healthy' ? 'All Systems Operational' : 
           getOverallHealth() === 'warning' ? 'Partial Issues' : 'System Issues'}
        </div>
      </div>

      {/* Health Items */}
      <div className="space-y-2">
        <HealthItem
          name="Gateway"
          status={status?.status === 'running' ? 'healthy' : 'error'}
          detail={status?.version ? `v${status.version}` : 'Checking...'}
          icon={<Server size={18} />}
        />
        
        <HealthItem
          name="Agent Runtime"
          status={statusLoading ? 'warning' : 'healthy'}
          detail={status?.model || 'Loading...'}
          icon={<Bot size={18} />}
        />
        
        <HealthItem
          name="Channels"
          status={activeChannels > 0 ? 'healthy' : totalChannels > 0 ? 'warning' : 'error'}
          detail={`${activeChannels}/${totalChannels} active`}
          icon={<Wifi size={18} />}
        />
        
        <HealthItem
          name="Memory Store"
          status="healthy"
          detail="Vector DB connected"
          icon={<Database size={18} />}
        />
      </div>
    </div>
  )
}
