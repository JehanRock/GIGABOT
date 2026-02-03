import { useUIStore, UserMode } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import { Sparkles, Wrench } from 'lucide-react'

interface UserModeToggleProps {
  className?: string
  showLabels?: boolean
}

export function UserModeToggle({ className, showLabels = true }: UserModeToggleProps) {
  const { userMode, setUserMode } = useUIStore()

  const modes: { id: UserMode; label: string; description: string; icon: React.ReactNode }[] = [
    {
      id: 'standard',
      label: 'Simple',
      description: 'Streamlined experience',
      icon: <Sparkles size={16} />,
    },
    {
      id: 'advanced',
      label: 'Advanced',
      description: 'Full control & customization',
      icon: <Wrench size={16} />,
    },
  ]

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {showLabels && (
        <label className="text-sm font-medium text-gray-300">Dashboard Mode</label>
      )}
      <div className="relative flex bg-giga-dark rounded-lg p-1 border border-giga-border">
        {/* Animated background pill */}
        <div
          className={cn(
            'absolute top-1 bottom-1 rounded-md bg-giga-accent transition-all duration-300 ease-out',
            userMode === 'standard' ? 'left-1 w-[calc(50%-4px)]' : 'left-[calc(50%+2px)] w-[calc(50%-4px)]'
          )}
        />
        
        {modes.map((mode) => (
          <button
            key={mode.id}
            onClick={() => setUserMode(mode.id)}
            className={cn(
              'relative flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md',
              'text-sm font-medium transition-colors duration-200 z-10',
              userMode === mode.id
                ? 'text-white'
                : 'text-gray-400 hover:text-gray-200'
            )}
          >
            {mode.icon}
            <span>{mode.label}</span>
          </button>
        ))}
      </div>
      
      {/* Description */}
      <p className="text-xs text-gray-500">
        {userMode === 'standard' 
          ? 'Simplified interface focused on essential features and autonomous operation.'
          : 'Full access to all features, configurations, and detailed system controls.'}
      </p>
    </div>
  )
}

// Compact version for header/sidebar
export function UserModeToggleCompact({ className }: { className?: string }) {
  const { userMode, setUserMode } = useUIStore()

  return (
    <button
      onClick={() => setUserMode(userMode === 'standard' ? 'advanced' : 'standard')}
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
        'border transition-all duration-200',
        userMode === 'standard'
          ? 'bg-giga-accent/20 border-giga-accent/50 text-giga-accent'
          : 'bg-purple-500/20 border-purple-500/50 text-purple-400',
        className
      )}
      title={`Switch to ${userMode === 'standard' ? 'Advanced' : 'Simple'} mode`}
    >
      {userMode === 'standard' ? (
        <>
          <Sparkles size={12} />
          <span>Simple</span>
        </>
      ) : (
        <>
          <Wrench size={12} />
          <span>Advanced</span>
        </>
      )}
    </button>
  )
}
