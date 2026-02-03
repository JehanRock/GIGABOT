import { 
  User, 
  MessageSquare, 
  Clock, 
  Zap,
  DollarSign,
  StickyNote,
  Plus
} from 'lucide-react'
import { useStatus, useTracking } from '@/hooks/useStatus'
import { formatCompactNumber, formatCurrency } from '@/lib/utils'

export function ChatDetailPanel() {
  const { data: status } = useStatus()
  const { data: tracking } = useTracking()

  const stats = tracking?.session || {
    total_tokens: 0,
    estimated_cost: 0,
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <h3 className="font-semibold text-white text-sm">Session Details</h3>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Session Info */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-giga-accent/20 flex items-center justify-center">
              <User size={24} className="text-giga-accent" />
            </div>
            <div>
              <p className="font-medium text-white">Web Session</p>
              <p className="text-xs text-gray-500">webui:default</p>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Statistics
          </h4>
          
          <div className="grid grid-cols-2 gap-2">
            <StatCard
              icon={<Zap size={14} />}
              label="Tokens"
              value={formatCompactNumber(stats.total_tokens)}
              color="text-giga-accent"
            />
            <StatCard
              icon={<DollarSign size={14} />}
              label="Cost"
              value={formatCurrency(stats.estimated_cost)}
              color="text-giga-success"
            />
            <StatCard
              icon={<MessageSquare size={14} />}
              label="Messages"
              value="--"
              color="text-purple-400"
            />
            <StatCard
              icon={<Clock size={14} />}
              label="Duration"
              value="--"
              color="text-blue-400"
            />
          </div>
        </div>

        {/* Model Info */}
        {status?.model && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Model
            </h4>
            <div className="px-3 py-2 bg-giga-card rounded-lg">
              <p className="text-sm text-white font-mono truncate">
                {status.model}
              </p>
            </div>
          </div>
        )}

        {/* Notes Section */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Notes
            </h4>
            <button className="p-1 rounded hover:bg-giga-hover transition-colors">
              <Plus size={14} className="text-gray-500" />
            </button>
          </div>
          
          <div className="p-3 bg-giga-card rounded-lg border border-sidebar-border">
            <div className="flex items-start gap-2 text-gray-500">
              <StickyNote size={14} className="flex-shrink-0 mt-0.5" />
              <p className="text-xs">
                Click + to add a note about this session...
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  color: string
}

function StatCard({ icon, label, value, color }: StatCardProps) {
  return (
    <div className="p-3 bg-giga-card rounded-lg border border-sidebar-border">
      <div className={`flex items-center gap-1.5 mb-1 ${color}`}>
        {icon}
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  )
}
