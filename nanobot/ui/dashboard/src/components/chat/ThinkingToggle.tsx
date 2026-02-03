import { Brain } from 'lucide-react'
import { cn } from '@/lib/utils'

type ThinkingLevel = 'low' | 'medium' | 'high'

interface ThinkingToggleProps {
  level: ThinkingLevel
  onLevelChange: (level: ThinkingLevel) => void
}

export function ThinkingToggle({ level, onLevelChange }: ThinkingToggleProps) {
  const levels: { id: ThinkingLevel; label: string; description: string }[] = [
    { id: 'low', label: 'Low', description: 'Quick responses' },
    { id: 'medium', label: 'Med', description: 'Balanced' },
    { id: 'high', label: 'High', description: 'Deep thinking' },
  ]

  return (
    <div className="flex items-center gap-2">
      <Brain size={14} className="text-gray-500" />
      <div className="flex bg-giga-dark rounded-lg p-0.5 border border-giga-border">
        {levels.map((l) => (
          <button
            key={l.id}
            onClick={() => onLevelChange(l.id)}
            className={cn(
              'px-2 py-1 text-xs font-medium rounded transition-colors',
              level === l.id
                ? 'bg-giga-accent text-white'
                : 'text-gray-500 hover:text-gray-300'
            )}
            title={l.description}
          >
            {l.label}
          </button>
        ))}
      </div>
    </div>
  )
}
