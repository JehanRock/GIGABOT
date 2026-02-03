import { GitBranch, Play, Square, Trash2, Eye, Plus, RotateCcw, CheckCircle, XCircle, Clock } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock data - TODO: Replace with real API
const mockSubAgents = [
  {
    id: 'sa-1',
    taskId: 'task-001',
    label: 'Research: TypeScript patterns',
    status: 'running' as const,
    progress: 65,
    startedAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    model: 'gpt-4',
  },
  {
    id: 'sa-2',
    taskId: 'task-002',
    label: 'Code review: API module',
    status: 'running' as const,
    progress: 30,
    startedAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    model: 'claude-3-opus',
  },
  {
    id: 'sa-3',
    taskId: 'task-003',
    label: 'Documentation generation',
    status: 'completed' as const,
    progress: 100,
    startedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    completedAt: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    result: 'Generated documentation for 12 modules',
    model: 'gpt-4-turbo',
  },
  {
    id: 'sa-4',
    taskId: 'task-004',
    label: 'Data analysis task',
    status: 'error' as const,
    progress: 45,
    startedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    completedAt: new Date(Date.now() - 1000 * 60 * 50).toISOString(),
    error: 'API rate limit exceeded',
    model: 'gpt-3.5-turbo',
  },
]

interface SubAgent {
  id: string
  taskId: string
  label: string
  status: 'running' | 'completed' | 'error' | 'stopped'
  progress?: number
  startedAt: string
  completedAt?: string
  result?: string
  error?: string
  model: string
}

function SubAgentCard({ 
  agent, 
  onStop, 
  onView,
  onDelete 
}: { 
  agent: SubAgent
  onStop?: () => void
  onView?: () => void
  onDelete?: () => void
}) {
  const getStatusIcon = () => {
    switch (agent.status) {
      case 'running':
        return <div className="w-2 h-2 rounded-full bg-giga-success animate-pulse" />
      case 'completed':
        return <CheckCircle size={16} className="text-giga-success" />
      case 'error':
        return <XCircle size={16} className="text-giga-error" />
      case 'stopped':
        return <Square size={16} className="text-gray-500" />
    }
  }

  const getStatusColor = () => {
    switch (agent.status) {
      case 'running':
        return 'border-giga-success/30'
      case 'completed':
        return 'border-giga-success/20'
      case 'error':
        return 'border-giga-error/30'
      default:
        return 'border-giga-border'
    }
  }

  return (
    <div className={cn('card p-4 border', getStatusColor())}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {getStatusIcon()}
            <h4 className="font-medium text-white truncate">{agent.label}</h4>
          </div>
          
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>Task: {agent.taskId}</span>
            <span>Model: {agent.model}</span>
          </div>

          {agent.status === 'running' && agent.progress !== undefined && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-400">Progress</span>
                <span className="text-giga-accent">{agent.progress}%</span>
              </div>
              <div className="h-1.5 bg-giga-dark rounded-full overflow-hidden">
                <div 
                  className="h-full bg-giga-accent rounded-full transition-all duration-300"
                  style={{ width: `${agent.progress}%` }}
                />
              </div>
            </div>
          )}

          {agent.result && (
            <p className="mt-2 text-sm text-giga-success">{agent.result}</p>
          )}

          {agent.error && (
            <p className="mt-2 text-sm text-giga-error">{agent.error}</p>
          )}
        </div>

        <div className="flex items-center gap-1">
          {agent.status === 'running' && onStop && (
            <button 
              onClick={onStop}
              className="p-2 rounded-lg text-gray-400 hover:text-giga-error hover:bg-giga-error/10 transition-colors"
              title="Stop"
            >
              <Square size={16} />
            </button>
          )}
          {onView && (
            <button 
              onClick={onView}
              className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
              title="View Details"
            >
              <Eye size={16} />
            </button>
          )}
          {agent.status !== 'running' && onDelete && (
            <button 
              onClick={onDelete}
              className="p-2 rounded-lg text-gray-400 hover:text-giga-error hover:bg-giga-error/10 transition-colors"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function SpawnAgentModal({ 
  isOpen, 
  onClose,
  onSpawn 
}: { 
  isOpen: boolean
  onClose: () => void
  onSpawn: (task: string, model: string) => void
}) {
  const [task, setTask] = useState('')
  const [model, setModel] = useState('gpt-4')

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-giga-card border border-giga-border rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-bold text-white mb-4">Spawn New Agent</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Task Description
            </label>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none resize-none"
              rows={3}
              placeholder="Describe the task for the sub-agent..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white focus:border-giga-accent focus:outline-none"
            >
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="claude-3-sonnet">Claude 3 Sonnet</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button 
            onClick={() => {
              onSpawn(task, model)
              onClose()
              setTask('')
            }}
            disabled={!task.trim()}
            className="btn-primary disabled:opacity-50"
          >
            Spawn Agent
          </button>
        </div>
      </div>
    </div>
  )
}

export function SubAgentsPanel() {
  const [showSpawnModal, setShowSpawnModal] = useState(false)
  const [filter, setFilter] = useState<'all' | 'running' | 'completed'>('all')

  const runningAgents = mockSubAgents.filter(a => a.status === 'running')
  const completedAgents = mockSubAgents.filter(a => a.status !== 'running')

  const filteredAgents = filter === 'all' 
    ? mockSubAgents 
    : filter === 'running' 
      ? runningAgents 
      : completedAgents

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
              <GitBranch size={20} className="text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Sub-Agents</h2>
              <p className="text-sm text-gray-400">
                {runningAgents.length} running, {completedAgents.length} completed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {runningAgents.length > 0 && (
              <button className="btn-secondary text-giga-error flex items-center gap-2">
                <Square size={16} />
                <span>Stop All</span>
              </button>
            )}
            <button 
              onClick={() => setShowSpawnModal(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Plus size={16} />
              <span>Spawn Agent</span>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          {(['all', 'running', 'completed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize',
                filter === f
                  ? 'bg-giga-accent text-white'
                  : 'text-gray-400 hover:text-white hover:bg-giga-hover'
              )}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Agent List */}
        <div className="space-y-3">
          {filteredAgents.length > 0 ? (
            filteredAgents.map((agent) => (
              <SubAgentCard
                key={agent.id}
                agent={agent}
                onStop={() => console.log('Stop', agent.id)}
                onView={() => console.log('View', agent.id)}
                onDelete={() => console.log('Delete', agent.id)}
              />
            ))
          ) : (
            <div className="card p-8 text-center">
              <GitBranch size={48} className="mx-auto text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-300 mb-2">No sub-agents</h3>
              <p className="text-sm text-gray-500 mb-4">
                {filter === 'all' 
                  ? 'No sub-agents have been spawned yet' 
                  : `No ${filter} sub-agents`}
              </p>
              <button 
                onClick={() => setShowSpawnModal(true)}
                className="btn-primary inline-flex items-center gap-2"
              >
                <Plus size={16} />
                <span>Spawn Agent</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <SpawnAgentModal
        isOpen={showSpawnModal}
        onClose={() => setShowSpawnModal(false)}
        onSpawn={(task, model) => console.log('Spawn:', task, model)}
      />
    </div>
  )
}
