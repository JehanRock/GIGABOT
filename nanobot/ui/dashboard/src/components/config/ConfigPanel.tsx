import { Code, ChevronRight, ChevronDown, Save, RotateCcw, AlertTriangle, Check, Edit2 } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock config data - TODO: Replace with real API
const mockConfig = {
  providers: {
    default_provider: 'openrouter',
    tier1_model: 'openai/gpt-4-turbo',
    tier2_model: 'anthropic/claude-3-sonnet',
    tier3_model: 'openai/gpt-3.5-turbo',
  },
  memory: {
    enabled: true,
    vector_store: 'chromadb',
    chunk_size: 512,
    top_k: 5,
  },
  channels: {
    telegram: {
      enabled: true,
      bot_token: '***HIDDEN***',
    },
    discord: {
      enabled: false,
      bot_token: '',
    },
  },
  security: {
    require_approval: false,
    audit_logging: true,
    sandbox_mode: false,
  },
  agent: {
    max_iterations: 10,
    thinking_budget: 'medium',
    auto_compact: true,
  },
}

type ConfigValue = string | number | boolean | Record<string, any>

interface ConfigNodeProps {
  name: string
  value: ConfigValue
  path: string[]
  level: number
  onEdit: (path: string[], value: ConfigValue) => void
}

function ConfigNode({ name, value, path, level, onEdit }: ConfigNodeProps) {
  const [expanded, setExpanded] = useState(level < 2)
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(String(value))

  const isObject = typeof value === 'object' && value !== null
  const isBoolean = typeof value === 'boolean'
  const isNumber = typeof value === 'number'

  const handleSave = () => {
    let newValue: ConfigValue = editValue
    if (isNumber) newValue = Number(editValue)
    if (isBoolean) newValue = editValue === 'true'
    onEdit(path, newValue)
    setEditing(false)
  }

  if (isObject) {
    return (
      <div className="border-l border-giga-border ml-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 py-1 px-2 w-full text-left hover:bg-giga-hover rounded-r transition-colors"
        >
          {expanded ? (
            <ChevronDown size={14} className="text-gray-500" />
          ) : (
            <ChevronRight size={14} className="text-gray-500" />
          )}
          <span className="text-purple-400 font-medium">{name}</span>
          <span className="text-gray-600 text-xs ml-2">
            {Object.keys(value).length} items
          </span>
        </button>
        {expanded && (
          <div className="ml-2">
            {Object.entries(value).map(([key, val]) => (
              <ConfigNode
                key={key}
                name={key}
                value={val as ConfigValue}
                path={[...path, key]}
                level={level + 1}
                onEdit={onEdit}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 py-1 px-2 ml-2 hover:bg-giga-hover rounded transition-colors group">
      <span className="text-cyan-400">{name}</span>
      <span className="text-gray-600">:</span>
      
      {editing ? (
        <div className="flex items-center gap-2 flex-1">
          {isBoolean ? (
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="px-2 py-0.5 bg-giga-dark border border-giga-accent rounded text-sm text-white focus:outline-none"
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          ) : (
            <input
              type={isNumber ? 'number' : 'text'}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="flex-1 px-2 py-0.5 bg-giga-dark border border-giga-accent rounded text-sm text-white focus:outline-none"
            />
          )}
          <button onClick={handleSave} className="p-1 text-giga-success hover:bg-giga-success/20 rounded">
            <Check size={14} />
          </button>
          <button onClick={() => setEditing(false)} className="p-1 text-gray-400 hover:bg-giga-hover rounded">
            <RotateCcw size={14} />
          </button>
        </div>
      ) : (
        <>
          <span className={cn(
            isBoolean ? (value ? 'text-giga-success' : 'text-giga-error') : '',
            isNumber ? 'text-orange-400' : '',
            typeof value === 'string' ? 'text-green-400' : ''
          )}>
            {isBoolean ? String(value) : typeof value === 'string' ? `"${value}"` : value}
          </span>
          <button 
            onClick={() => {
              setEditValue(String(value))
              setEditing(true)
            }}
            className="p-1 text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Edit2 size={12} />
          </button>
        </>
      )}
    </div>
  )
}

function JsonEditor({ 
  config, 
  onChange 
}: { 
  config: Record<string, any>
  onChange: (config: Record<string, any>) => void 
}) {
  const [jsonText, setJsonText] = useState(JSON.stringify(config, null, 2))
  const [error, setError] = useState<string | null>(null)

  const handleChange = (text: string) => {
    setJsonText(text)
    try {
      const parsed = JSON.parse(text)
      setError(null)
      onChange(parsed)
    } catch (e) {
      setError('Invalid JSON')
    }
  }

  return (
    <div className="h-full flex flex-col">
      {error && (
        <div className="flex items-center gap-2 p-2 bg-giga-error/20 text-giga-error text-sm">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}
      <textarea
        value={jsonText}
        onChange={(e) => handleChange(e.target.value)}
        className="flex-1 p-4 bg-giga-dark font-mono text-sm text-gray-300 resize-none focus:outline-none"
        spellCheck={false}
      />
    </div>
  )
}

export function ConfigPanel() {
  const [config, setConfig] = useState(mockConfig)
  const [viewMode, setViewMode] = useState<'tree' | 'json'>('tree')
  const [hasChanges, setHasChanges] = useState(false)

  const handleEdit = (path: string[], value: ConfigValue) => {
    const newConfig = { ...config }
    let current: any = newConfig
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]]
    }
    current[path[path.length - 1]] = value
    setConfig(newConfig)
    setHasChanges(true)
  }

  const handleSave = () => {
    console.log('Saving config:', config)
    setHasChanges(false)
  }

  const handleReset = () => {
    setConfig(mockConfig)
    setHasChanges(false)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-giga-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
              <Code size={20} className="text-indigo-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Configuration</h2>
              <p className="text-sm text-gray-400">
                System configuration editor
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex bg-giga-dark rounded-lg p-1 border border-giga-border">
              <button
                onClick={() => setViewMode('tree')}
                className={cn(
                  'px-3 py-1 text-sm rounded transition-colors',
                  viewMode === 'tree' ? 'bg-giga-accent text-white' : 'text-gray-400 hover:text-white'
                )}
              >
                Tree
              </button>
              <button
                onClick={() => setViewMode('json')}
                className={cn(
                  'px-3 py-1 text-sm rounded transition-colors',
                  viewMode === 'json' ? 'bg-giga-accent text-white' : 'text-gray-400 hover:text-white'
                )}
              >
                JSON
              </button>
            </div>
            
            {hasChanges && (
              <>
                <button onClick={handleReset} className="btn-secondary flex items-center gap-2">
                  <RotateCcw size={16} />
                  <span>Reset</span>
                </button>
                <button onClick={handleSave} className="btn-primary flex items-center gap-2">
                  <Save size={16} />
                  <span>Save</span>
                </button>
              </>
            )}
          </div>
        </div>

        {hasChanges && (
          <div className="mt-4 flex items-center gap-2 p-2 bg-giga-warning/20 rounded-lg text-sm text-giga-warning">
            <AlertTriangle size={14} />
            You have unsaved changes
          </div>
        )}
      </div>

      {/* Config Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === 'tree' ? (
          <div className="p-4 font-mono text-sm">
            {Object.entries(config).map(([key, value]) => (
              <ConfigNode
                key={key}
                name={key}
                value={value}
                path={[key]}
                level={0}
                onEdit={handleEdit}
              />
            ))}
          </div>
        ) : (
          <JsonEditor 
            config={config} 
            onChange={(newConfig) => {
              setConfig(newConfig as typeof mockConfig)
              setHasChanges(true)
            }} 
          />
        )}
      </div>
    </div>
  )
}
