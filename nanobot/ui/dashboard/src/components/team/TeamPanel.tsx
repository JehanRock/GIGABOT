import { UsersRound, Shield, Code, Search, MessageSquare, CheckCircle, AlertTriangle, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock data - TODO: Replace with real API
const mockRoles = [
  {
    id: 'lead',
    name: 'Lead',
    description: 'Coordinates team and makes final decisions',
    model: 'gpt-4',
    status: 'active' as const,
    color: 'purple',
  },
  {
    id: 'researcher',
    name: 'Researcher',
    description: 'Gathers information and analyzes data',
    model: 'claude-3-opus',
    status: 'active' as const,
    color: 'blue',
  },
  {
    id: 'coder',
    name: 'Coder',
    description: 'Implements solutions and writes code',
    model: 'gpt-4-turbo',
    status: 'active' as const,
    color: 'green',
  },
  {
    id: 'reviewer',
    name: 'Reviewer',
    description: 'Reviews work and provides feedback',
    model: 'claude-3-sonnet',
    status: 'inactive' as const,
    color: 'orange',
  },
]

const mockPatterns = [
  { id: 'research', name: 'Research', description: 'Deep information gathering' },
  { id: 'code', name: 'Code', description: 'Implementation focused' },
  { id: 'review', name: 'Review', description: 'Quality assurance' },
  { id: 'brainstorm', name: 'Brainstorm', description: 'Creative problem solving' },
]

interface Role {
  id: string
  name: string
  description: string
  model: string
  status: 'active' | 'inactive'
  color: string
}

function RoleCard({ role, onEdit }: { role: Role; onEdit?: () => void }) {
  const getColorClass = () => {
    switch (role.color) {
      case 'purple': return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
      case 'blue': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'green': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'orange': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  const getIcon = () => {
    switch (role.id) {
      case 'lead': return <Shield size={20} />
      case 'researcher': return <Search size={20} />
      case 'coder': return <Code size={20} />
      case 'reviewer': return <CheckCircle size={20} />
      default: return <MessageSquare size={20} />
    }
  }

  return (
    <div className={cn('card p-4 border', role.status === 'inactive' && 'opacity-60')}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border', getColorClass())}>
            {getIcon()}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-medium text-white">{role.name}</h4>
              <span className={cn(
                'px-1.5 py-0.5 text-[10px] font-medium rounded',
                role.status === 'active' ? 'bg-giga-success/20 text-giga-success' : 'bg-gray-500/20 text-gray-400'
              )}>
                {role.status}
              </span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{role.description}</p>
            <p className="text-xs text-gray-500 mt-2">Model: {role.model}</p>
          </div>
        </div>
        <button 
          onClick={onEdit}
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
        >
          <Settings2 size={16} />
        </button>
      </div>
    </div>
  )
}

function QualityGateStatus() {
  return (
    <div className="card p-4">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Shield size={16} className="text-giga-accent" />
        Quality Gate
      </h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Code Review</span>
          <div className="flex items-center gap-2">
            <CheckCircle size={14} className="text-giga-success" />
            <span className="text-sm text-giga-success">Passed</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Security Audit</span>
          <div className="flex items-center gap-2">
            <CheckCircle size={14} className="text-giga-success" />
            <span className="text-sm text-giga-success">Passed</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Documentation</span>
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-giga-warning" />
            <span className="text-sm text-giga-warning">Pending</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export function TeamPanel() {
  const [activePattern, setActivePattern] = useState('research')

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500/20 flex items-center justify-center">
              <UsersRound size={20} className="text-orange-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Team / Swarm</h2>
              <p className="text-sm text-gray-400">
                {mockRoles.filter(r => r.status === 'active').length} active roles
              </p>
            </div>
          </div>
        </div>

        {/* Swarm Patterns */}
        <div className="card p-4">
          <h3 className="font-medium text-white mb-4">Swarm Pattern</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {mockPatterns.map((pattern) => (
              <button
                key={pattern.id}
                onClick={() => setActivePattern(pattern.id)}
                className={cn(
                  'p-3 rounded-lg text-left transition-colors border',
                  activePattern === pattern.id
                    ? 'bg-giga-accent/20 border-giga-accent text-white'
                    : 'bg-giga-dark border-giga-border text-gray-400 hover:text-white hover:border-giga-border-hover'
                )}
              >
                <div className="font-medium text-sm">{pattern.name}</div>
                <div className="text-xs mt-1 opacity-70">{pattern.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Team Roster */}
        <div>
          <h3 className="font-medium text-white mb-4">Team Roster</h3>
          <div className="grid gap-3">
            {mockRoles.map((role) => (
              <RoleCard 
                key={role.id} 
                role={role}
                onEdit={() => console.log('Edit role:', role.id)}
              />
            ))}
          </div>
        </div>

        {/* Quality Gate */}
        <QualityGateStatus />
      </div>
    </div>
  )
}
