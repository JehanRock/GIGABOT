import { Bug, Activity, Server, Cpu, Database, Wifi, CheckCircle, XCircle, AlertTriangle, Send, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock debug data - TODO: Replace with real API
const mockSystemStatus = {
  uptime: '3d 14h 22m',
  version: '0.1.0',
  python: '3.11.5',
  memory_usage: '256MB / 1GB',
  cpu_usage: '12%',
  active_connections: 3,
  pending_tasks: 2,
}

const mockHealthChecks = [
  { id: 'gateway', name: 'API Gateway', status: 'healthy' as const, latency: '12ms' },
  { id: 'litellm', name: 'LiteLLM Provider', status: 'healthy' as const, latency: '45ms' },
  { id: 'memory', name: 'Memory Store', status: 'healthy' as const, latency: '8ms' },
  { id: 'vector', name: 'Vector DB', status: 'healthy' as const, latency: '15ms' },
  { id: 'telegram', name: 'Telegram Channel', status: 'healthy' as const, latency: '120ms' },
  { id: 'discord', name: 'Discord Channel', status: 'unhealthy' as const, latency: '-', error: 'Not configured' },
  { id: 'cron', name: 'Cron Service', status: 'healthy' as const, latency: '2ms' },
  { id: 'websocket', name: 'WebSocket', status: 'degraded' as const, latency: '250ms', error: 'High latency' },
]

const mockModels = [
  { id: 'gpt-4', name: 'GPT-4', provider: 'openai', available: true },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', provider: 'openai', available: true },
  { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'openai', available: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', provider: 'anthropic', available: true },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', provider: 'anthropic', available: true },
  { id: 'llama-2-70b', name: 'Llama 2 70B', provider: 'together', available: false },
]

interface HealthCheck {
  id: string
  name: string
  status: 'healthy' | 'unhealthy' | 'degraded'
  latency: string
  error?: string
}

function StatusSnapshot() {
  return (
    <div className="card p-4">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Server size={16} className="text-giga-accent" />
        System Status
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-gray-500">Uptime</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.uptime}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Version</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.version}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Memory</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.memory_usage}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">CPU</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.cpu_usage}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Python</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.python}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Connections</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.active_connections}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Pending Tasks</p>
          <p className="text-sm text-white font-medium">{mockSystemStatus.pending_tasks}</p>
        </div>
      </div>
    </div>
  )
}

function HealthChecks({ checks }: { checks: HealthCheck[] }) {
  const getStatusIcon = (status: HealthCheck['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle size={14} className="text-giga-success" />
      case 'unhealthy':
        return <XCircle size={14} className="text-giga-error" />
      case 'degraded':
        return <AlertTriangle size={14} className="text-giga-warning" />
    }
  }

  return (
    <div className="card p-4">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Activity size={16} className="text-giga-accent" />
        Health Checks
      </h3>
      <div className="space-y-2">
        {checks.map((check) => (
          <div 
            key={check.id}
            className="flex items-center justify-between p-2 rounded-lg bg-giga-dark"
          >
            <div className="flex items-center gap-3">
              {getStatusIcon(check.status)}
              <span className="text-sm text-gray-300">{check.name}</span>
            </div>
            <div className="flex items-center gap-4">
              {check.error && (
                <span className="text-xs text-gray-500">{check.error}</span>
              )}
              <span className={cn(
                'text-xs font-mono',
                check.status === 'healthy' ? 'text-giga-success' : 'text-gray-500'
              )}>
                {check.latency}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ModelsList() {
  return (
    <div className="card p-4">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Cpu size={16} className="text-giga-accent" />
        Available Models
      </h3>
      <div className="space-y-2">
        {mockModels.map((model) => (
          <div 
            key={model.id}
            className={cn(
              'flex items-center justify-between p-2 rounded-lg bg-giga-dark',
              !model.available && 'opacity-50'
            )}
          >
            <div className="flex items-center gap-3">
              {model.available ? (
                <CheckCircle size={14} className="text-giga-success" />
              ) : (
                <XCircle size={14} className="text-gray-500" />
              )}
              <span className="text-sm text-gray-300">{model.name}</span>
            </div>
            <span className="text-xs text-gray-500">{model.provider}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function RpcConsole() {
  const [endpoint, setEndpoint] = useState('/api/status')
  const [method, setMethod] = useState('GET')
  const [body, setBody] = useState('')
  const [response, setResponse] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSend = async () => {
    setLoading(true)
    // Mock response - TODO: Replace with real API call
    await new Promise(resolve => setTimeout(resolve, 500))
    setResponse(JSON.stringify({
      status: 'ok',
      timestamp: new Date().toISOString(),
      data: { message: 'Mock response' }
    }, null, 2))
    setLoading(false)
  }

  return (
    <div className="card p-4">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Wifi size={16} className="text-giga-accent" />
        RPC Console
      </h3>
      
      <div className="space-y-4">
        <div className="flex gap-2">
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white focus:border-giga-accent focus:outline-none"
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
          </select>
          <input
            type="text"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            className="flex-1 px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white font-mono text-sm placeholder-gray-500 focus:border-giga-accent focus:outline-none"
            placeholder="/api/..."
          />
          <button 
            onClick={handleSend}
            disabled={loading}
            className="btn-primary flex items-center gap-2"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
            <span>Send</span>
          </button>
        </div>

        {method !== 'GET' && (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white font-mono text-sm placeholder-gray-500 focus:border-giga-accent focus:outline-none resize-none"
            rows={3}
            placeholder='{"key": "value"}'
          />
        )}

        {response && (
          <div className="bg-giga-dark rounded-lg p-4 font-mono text-sm text-gray-300 overflow-x-auto">
            <pre>{response}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

export function DebugPanel() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
              <Bug size={20} className="text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Debug</h2>
              <p className="text-sm text-gray-400">System diagnostics and testing</p>
            </div>
          </div>
          <button className="btn-secondary flex items-center gap-2">
            <RefreshCw size={16} />
            <span>Refresh All</span>
          </button>
        </div>

        <StatusSnapshot />
        <HealthChecks checks={mockHealthChecks} />
        <ModelsList />
        <RpcConsole />
      </div>
    </div>
  )
}
