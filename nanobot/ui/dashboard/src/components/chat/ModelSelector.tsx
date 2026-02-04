import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Cpu, Check, Zap, Brain, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Model {
  id: string
  name: string
  provider: string
  tier: 'tier1' | 'tier2' | 'tier3'
  description: string
}

const models: Model[] = [
  // Tier 1 - Flagship Models
  { id: 'anthropic/claude-opus-4-5', name: 'Claude Opus 4.5', provider: 'Anthropic', tier: 'tier1', description: 'Top-tier reasoning and analysis' },
  { id: 'anthropic/claude-sonnet-4-5', name: 'Claude Sonnet 4.5', provider: 'Anthropic', tier: 'tier1', description: 'Most used, balanced price/performance' },
  { id: 'google/gemini-3-pro-preview', name: 'Gemini 3 Pro', provider: 'Google', tier: 'tier1', description: 'Flagship Google model, multimodal' },
  { id: 'openai/gpt-4o', name: 'GPT-4o', provider: 'OpenAI', tier: 'tier1', description: 'OpenAI flagship, multimodal' },
  // Tier 2 - Fast & Efficient
  { id: 'google/gemini-3-flash-preview', name: 'Gemini 3 Flash', provider: 'Google', tier: 'tier2', description: 'Fast and efficient, great for quick tasks' },
  { id: 'anthropic/claude-3.5-haiku', name: 'Claude 3.5 Haiku', provider: 'Anthropic', tier: 'tier2', description: 'Ultra-fast, great for simple tasks' },
  { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', tier: 'tier2', description: 'Fast and cheap, good for quick tasks' },
  { id: 'deepseek/deepseek-chat', name: 'DeepSeek Chat', provider: 'DeepSeek', tier: 'tier2', description: 'Strong coding model, low cost' },
  // Tier 3 - Budget
  { id: 'google/gemini-2.0-flash-exp:free', name: 'Gemini 2.0 Flash (Free)', provider: 'Google', tier: 'tier3', description: 'Free tier, limited rate' },
  { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B', provider: 'Meta', tier: 'tier3', description: 'Open source, good general use' },
]

interface ModelSelectorProps {
  selectedModel: string
  onModelChange: (modelId: string) => void
}

export function ModelSelector({ selectedModel, onModelChange }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selected = models.find(m => m.id === selectedModel) || models[0]

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const getTierIcon = (tier: string) => {
    switch (tier) {
      case 'tier1': return <Brain size={14} className="text-purple-400" />
      case 'tier2': return <Sparkles size={14} className="text-blue-400" />
      case 'tier3': return <Zap size={14} className="text-green-400" />
      default: return <Cpu size={14} />
    }
  }

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'tier1': return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
      case 'tier2': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'tier3': return 'bg-green-500/20 text-green-400 border-green-500/30'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors text-sm',
          isOpen 
            ? 'bg-giga-accent/20 border-giga-accent text-white'
            : 'bg-giga-card border-giga-border text-gray-300 hover:border-giga-accent'
        )}
      >
        {getTierIcon(selected.tier)}
        <span className="truncate max-w-[120px]">{selected.name}</span>
        <ChevronDown size={14} className={cn('transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-1 w-72 bg-giga-card border border-giga-border rounded-xl shadow-xl overflow-hidden z-50">
          <div className="p-2 border-b border-giga-border">
            <p className="text-xs text-gray-500 px-2">Select Model</p>
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {models.map((model) => (
              <button
                key={model.id}
                onClick={() => {
                  onModelChange(model.id)
                  setIsOpen(false)
                }}
                className={cn(
                  'w-full flex items-start gap-3 p-3 hover:bg-giga-hover transition-colors text-left',
                  selectedModel === model.id && 'bg-giga-hover'
                )}
              >
                <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center border flex-shrink-0', getTierColor(model.tier))}>
                  {getTierIcon(model.tier)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-white">{model.name}</span>
                    {selectedModel === model.id && (
                      <Check size={14} className="text-giga-accent flex-shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{model.provider}</p>
                  <p className="text-xs text-gray-400 mt-1">{model.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
