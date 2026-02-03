import { useState } from 'react'
import { 
  ChevronDown, 
  ChevronRight, 
  Terminal, 
  Check, 
  Loader2, 
  AlertCircle,
  Code
} from 'lucide-react'
import type { ToolCall } from '@/types'
import { cn } from '@/lib/utils'

interface ToolOutputCardProps {
  toolCall: ToolCall
}

export function ToolOutputCard({ toolCall }: ToolOutputCardProps) {
  const [expanded, setExpanded] = useState(false)

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case 'completed':
        return <Check size={14} className="text-giga-success" />
      case 'running':
        return <Loader2 size={14} className="text-giga-accent animate-spin" />
      case 'error':
        return <AlertCircle size={14} className="text-giga-error" />
      default:
        return <Terminal size={14} className="text-gray-400" />
    }
  }

  const getStatusText = () => {
    switch (toolCall.status) {
      case 'completed':
        return 'Completed'
      case 'running':
        return 'Running...'
      case 'error':
        return 'Error'
      default:
        return 'Pending'
    }
  }

  const getStatusColor = () => {
    switch (toolCall.status) {
      case 'completed':
        return 'border-giga-success/30 bg-giga-success/5'
      case 'running':
        return 'border-giga-accent/30 bg-giga-accent/5'
      case 'error':
        return 'border-giga-error/30 bg-giga-error/5'
      default:
        return 'border-sidebar-border bg-giga-card'
    }
  }

  return (
    <div className={cn(
      'rounded-lg border overflow-hidden transition-all duration-200',
      getStatusColor()
    )}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-white/5 transition-colors"
      >
        <span className="flex-shrink-0">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        
        <Code size={14} className="text-giga-accent flex-shrink-0" />
        
        <span className="flex-1 text-left text-sm font-mono text-gray-300 truncate">
          {toolCall.name}
        </span>
        
        <div className="flex items-center gap-1.5 text-xs">
          {getStatusIcon()}
          <span className="text-gray-500">{getStatusText()}</span>
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-white/10">
          {/* Arguments */}
          {Object.keys(toolCall.arguments).length > 0 && (
            <div className="mt-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                Arguments
              </p>
              <pre className="text-xs bg-giga-darker rounded p-2 overflow-x-auto text-gray-300 font-mono">
                {JSON.stringify(toolCall.arguments, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {toolCall.result && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                Result
              </p>
              <pre className="text-xs bg-giga-darker rounded p-2 overflow-x-auto text-gray-300 font-mono max-h-[200px]">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
