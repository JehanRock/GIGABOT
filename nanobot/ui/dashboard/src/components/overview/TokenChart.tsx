import { useState } from 'react'
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  CartesianGrid
} from 'recharts'
import { cn } from '@/lib/utils'

// Mock data - in production this would come from the API
const generateMockData = () => {
  const hours = []
  for (let i = 0; i < 24; i++) {
    hours.push({
      hour: `${i.toString().padStart(2, '0')}:00`,
      tokens: Math.floor(Math.random() * 10000) + 1000,
      cost: Math.random() * 0.5,
    })
  }
  return hours
}

type TimeRange = '24h' | '7d' | '30d'

export function TokenChart() {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h')
  const data = generateMockData()

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-white">Token Usage</h3>
          <p className="text-xs text-gray-500 mt-0.5">Usage over time</p>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex gap-1 bg-giga-darker rounded-lg p-1">
          {(['24h', '7d', '30d'] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-md transition-colors',
                timeRange === range
                  ? 'bg-giga-accent text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
            <XAxis 
              dataKey="hour" 
              stroke="#6b7280" 
              fontSize={10}
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              stroke="#6b7280" 
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${(value / 1000).toFixed(0)}K`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#252540',
                border: '1px solid #2e2e42',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#6366f1' }}
              formatter={(value: number) => [value.toLocaleString(), 'Tokens']}
            />
            <Area
              type="monotone"
              dataKey="tokens"
              stroke="#6366f1"
              strokeWidth={2}
              fill="url(#tokenGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
