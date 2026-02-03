import { useState, useEffect } from 'react'
import { FileText, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ContextMeterProps {
  usedTokens: number
  maxTokens: number
}

export function ContextMeter({ usedTokens, maxTokens }: ContextMeterProps) {
  const percentage = Math.min((usedTokens / maxTokens) * 100, 100)
  const isWarning = percentage > 70
  const isCritical = percentage > 90

  const getColor = () => {
    if (isCritical) return 'bg-giga-error'
    if (isWarning) return 'bg-giga-warning'
    return 'bg-giga-accent'
  }

  const getBgColor = () => {
    if (isCritical) return 'bg-giga-error/20'
    if (isWarning) return 'bg-giga-warning/20'
    return 'bg-giga-accent/20'
  }

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}k`
    }
    return tokens.toString()
  }

  return (
    <div className="flex items-center gap-2">
      {isCritical ? (
        <AlertTriangle size={14} className="text-giga-error" />
      ) : (
        <FileText size={14} className="text-gray-500" />
      )}
      <div className="flex items-center gap-2">
        <div className={cn('w-20 h-1.5 rounded-full overflow-hidden', getBgColor())}>
          <div 
            className={cn('h-full rounded-full transition-all duration-300', getColor())}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className={cn(
          'text-xs font-mono',
          isCritical ? 'text-giga-error' : isWarning ? 'text-giga-warning' : 'text-gray-500'
        )}>
          {formatTokens(usedTokens)}/{formatTokens(maxTokens)}
        </span>
      </div>
    </div>
  )
}

// Compact version for inline display
export function ContextMeterCompact({ usedTokens, maxTokens }: ContextMeterProps) {
  const percentage = Math.min((usedTokens / maxTokens) * 100, 100)
  const isCritical = percentage > 90

  return (
    <div 
      className={cn(
        'px-2 py-1 rounded text-xs font-mono',
        isCritical 
          ? 'bg-giga-error/20 text-giga-error' 
          : 'bg-giga-dark text-gray-400'
      )}
      title={`Context: ${usedTokens} / ${maxTokens} tokens`}
    >
      {Math.round(percentage)}%
    </div>
  )
}
