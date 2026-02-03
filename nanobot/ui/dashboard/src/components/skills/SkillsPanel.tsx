import { Puzzle, Check, X, Settings2, Download, ExternalLink, Key, AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock data - TODO: Replace with real API
const mockSkills = [
  {
    id: 'github',
    name: 'GitHub',
    description: 'Interact with GitHub repositories, issues, and pull requests',
    enabled: true,
    hasApiKey: true,
    icon: '🐙',
    category: 'Integration',
    requirements: { bins: ['git'], env: ['GITHUB_TOKEN'] },
    requirementsMet: true,
  },
  {
    id: 'weather',
    name: 'Weather',
    description: 'Get current weather and forecasts for any location',
    enabled: true,
    hasApiKey: true,
    icon: '🌤️',
    category: 'Utility',
    requirements: { bins: [], env: ['OPENWEATHER_API_KEY'] },
    requirementsMet: true,
  },
  {
    id: 'summarize',
    name: 'Summarize',
    description: 'Summarize long texts, articles, and documents',
    enabled: true,
    hasApiKey: false,
    icon: '📝',
    category: 'AI',
    requirements: { bins: [], env: [] },
    requirementsMet: true,
  },
  {
    id: 'tmux',
    name: 'Tmux',
    description: 'Manage terminal sessions with tmux',
    enabled: false,
    hasApiKey: false,
    icon: '💻',
    category: 'System',
    requirements: { bins: ['tmux'], env: [] },
    requirementsMet: false,
  },
  {
    id: 'skill-creator',
    name: 'Skill Creator',
    description: 'Create new skills dynamically',
    enabled: true,
    hasApiKey: false,
    icon: '🔧',
    category: 'Meta',
    requirements: { bins: [], env: [] },
    requirementsMet: true,
  },
]

interface Skill {
  id: string
  name: string
  description: string
  enabled: boolean
  hasApiKey: boolean
  icon: string
  category: string
  requirements: { bins: string[]; env: string[] }
  requirementsMet: boolean
}

function SkillCard({ 
  skill, 
  onToggle, 
  onConfigure,
  onView 
}: { 
  skill: Skill
  onToggle?: () => void
  onConfigure?: () => void
  onView?: () => void
}) {
  return (
    <div className={cn(
      'card p-4 border transition-all',
      skill.enabled ? 'border-giga-border' : 'border-giga-border opacity-60',
      !skill.requirementsMet && 'border-giga-warning/30'
    )}>
      <div className="flex items-start gap-4">
        <div className="text-3xl">{skill.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-white">{skill.name}</h4>
            <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-giga-dark text-gray-400">
              {skill.category}
            </span>
          </div>
          <p className="text-sm text-gray-400 mb-2">{skill.description}</p>
          
          {!skill.requirementsMet && (
            <div className="flex items-center gap-2 text-xs text-giga-warning">
              <AlertCircle size={12} />
              <span>Missing requirements: {skill.requirements.bins.join(', ')}</span>
            </div>
          )}

          {skill.requirements.env.length > 0 && (
            <div className="flex items-center gap-2 mt-2">
              <Key size={12} className={skill.hasApiKey ? 'text-giga-success' : 'text-gray-500'} />
              <span className="text-xs text-gray-500">
                {skill.hasApiKey ? 'API key configured' : 'API key required'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {skill.requirements.env.length > 0 && (
            <button 
              onClick={onConfigure}
              className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
              title="Configure API Key"
            >
              <Key size={16} />
            </button>
          )}
          <button 
            onClick={onView}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
            title="View Details"
          >
            <ExternalLink size={16} />
          </button>
          <button
            onClick={onToggle}
            disabled={!skill.requirementsMet}
            className={cn(
              'p-2 rounded-lg transition-colors',
              skill.enabled
                ? 'text-giga-success hover:text-gray-400'
                : 'text-gray-500 hover:text-giga-success',
              !skill.requirementsMet && 'opacity-50 cursor-not-allowed'
            )}
            title={skill.enabled ? 'Disable' : 'Enable'}
          >
            {skill.enabled ? <Check size={16} /> : <X size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}

function SkillConfigModal({ 
  isOpen, 
  skill,
  onClose,
  onSave 
}: { 
  isOpen: boolean
  skill: Skill | null
  onClose: () => void
  onSave: (skillId: string, config: Record<string, string>) => void
}) {
  const [apiKey, setApiKey] = useState('')

  if (!isOpen || !skill) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-giga-card border border-giga-border rounded-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">{skill.icon}</span>
          <h3 className="text-lg font-bold text-white">Configure {skill.name}</h3>
        </div>
        
        <div className="space-y-4">
          {skill.requirements.env.map((envVar) => (
            <div key={envVar}>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                {envVar}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none"
                placeholder="Enter API key..."
              />
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button 
            onClick={() => {
              onSave(skill.id, { apiKey })
              onClose()
            }}
            className="btn-primary"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

export function SkillsPanel() {
  const [configSkill, setConfigSkill] = useState<Skill | null>(null)
  const [filter, setFilter] = useState<'all' | 'enabled' | 'disabled'>('all')

  const categories = [...new Set(mockSkills.map(s => s.category))]
  
  const filteredSkills = mockSkills.filter(skill => {
    if (filter === 'enabled') return skill.enabled
    if (filter === 'disabled') return !skill.enabled
    return true
  })

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-pink-500/20 flex items-center justify-center">
              <Puzzle size={20} className="text-pink-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Skills</h2>
              <p className="text-sm text-gray-400">
                {mockSkills.filter(s => s.enabled).length} enabled, {mockSkills.length} total
              </p>
            </div>
          </div>
          <button className="btn-secondary flex items-center gap-2">
            <Download size={16} />
            <span>Browse Skills</span>
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          {(['all', 'enabled', 'disabled'] as const).map((f) => (
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

        {/* Skills by Category */}
        {categories.map((category) => {
          const categorySkills = filteredSkills.filter(s => s.category === category)
          if (categorySkills.length === 0) return null
          
          return (
            <div key={category}>
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                {category}
              </h3>
              <div className="space-y-3">
                {categorySkills.map((skill) => (
                  <SkillCard
                    key={skill.id}
                    skill={skill}
                    onToggle={() => console.log('Toggle', skill.id)}
                    onConfigure={() => setConfigSkill(skill)}
                    onView={() => console.log('View', skill.id)}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <SkillConfigModal
        isOpen={!!configSkill}
        skill={configSkill}
        onClose={() => setConfigSkill(null)}
        onSave={(id, config) => console.log('Save config:', id, config)}
      />
    </div>
  )
}
