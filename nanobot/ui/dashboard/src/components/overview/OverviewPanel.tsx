import { StatsGrid } from './StatsGrid'
import { TokenChart } from './TokenChart'
import { RecentActivity } from './RecentActivity'
import { SystemHealth } from './SystemHealth'
import { SimpleStatusCard } from './SimpleStatusCard'
import { useUIStore } from '@/stores/uiStore'

export function OverviewPanel() {
  const { userMode } = useUIStore()
  const isStandard = userMode === 'standard'

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            {isStandard 
              ? 'Your GigaBot status at a glance'
              : 'Monitor your GigaBot system performance and usage'}
          </p>
        </div>

        {isStandard ? (
          <>
            {/* Simplified view for standard users */}
            <SimpleStatusCard />
            <RecentActivity />
          </>
        ) : (
          <>
            {/* Full view for advanced users */}
            <StatsGrid />
            
            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <TokenChart />
              <SystemHealth />
            </div>

            {/* Recent Activity */}
            <RecentActivity />
          </>
        )}
      </div>
    </div>
  )
}
