import { 
  Zap, 
  DollarSign, 
  Users, 
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react'
import { useTracking, useStatus } from '@/hooks/useStatus'
import { useSessions } from '@/hooks/useSessions'
import { formatCompactNumber, formatCurrency, cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string
  subtitle?: string
  icon: React.ReactNode
  trend?: {
    value: number
    isPositive: boolean
  }
  color: string
}

function StatCard({ title, value, subtitle, icon, trend, color }: StatCardProps) {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className={`p-2 rounded-lg ${color}`}>
          {icon}
        </div>
        {trend && (
          <div className={cn(
            'flex items-center gap-1 text-xs font-medium',
            trend.isPositive ? 'text-giga-success' : 'text-giga-error'
          )}>
            {trend.isPositive ? (
              <ArrowUpRight size={14} />
            ) : (
              <ArrowDownRight size={14} />
            )}
            {Math.abs(trend.value)}%
          </div>
        )}
      </div>
      
      <div className="mt-4">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-xs text-gray-500 mt-1">{title}</p>
        {subtitle && (
          <p className="text-[10px] text-gray-600 mt-0.5">{subtitle}</p>
        )}
      </div>
    </div>
  )
}

export function StatsGrid() {
  const { data: tracking, isLoading: trackingLoading } = useTracking()
  const { data: status } = useStatus()
  const { data: sessions } = useSessions()

  const stats = tracking?.session || {
    total_tokens: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    estimated_cost: 0,
  }

  const sessionCount = sessions?.sessions?.length || 0
  const efficiency = tracking?.efficiency_score || 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {/* Token Usage */}
      <StatCard
        title="Token Usage"
        value={trackingLoading ? '--' : formatCompactNumber(stats.total_tokens)}
        subtitle={`${formatCompactNumber(stats.prompt_tokens)} in / ${formatCompactNumber(stats.completion_tokens)} out`}
        icon={<Zap size={20} className="text-giga-accent" />}
        color="bg-giga-accent/10"
        trend={{ value: 12, isPositive: true }}
      />

      {/* Estimated Cost */}
      <StatCard
        title="Estimated Cost"
        value={trackingLoading ? '--' : formatCurrency(stats.estimated_cost)}
        subtitle="Today"
        icon={<DollarSign size={20} className="text-giga-success" />}
        color="bg-giga-success/10"
      />

      {/* Active Sessions */}
      <StatCard
        title="Active Sessions"
        value={sessionCount.toString()}
        subtitle="Across all channels"
        icon={<Users size={20} className="text-purple-400" />}
        color="bg-purple-400/10"
        trend={{ value: 5, isPositive: true }}
      />

      {/* Efficiency Score */}
      <StatCard
        title="Efficiency Score"
        value={efficiency ? `${efficiency}%` : '--'}
        subtitle="Token optimization"
        icon={<TrendingUp size={20} className="text-blue-400" />}
        color="bg-blue-400/10"
        trend={{ value: 3, isPositive: true }}
      />
    </div>
  )
}
