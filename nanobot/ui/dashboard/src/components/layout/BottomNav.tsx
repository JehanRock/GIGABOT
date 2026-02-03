import { 
  MessageSquare, 
  LayoutDashboard, 
  Radio, 
  MoreHorizontal,
  Users,
  Settings,
  Activity,
  GitBranch,
  UsersRound,
  Clock,
  Puzzle,
  Network,
  FileText,
  Code,
  Bug
} from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'
import type { ViewType } from '@/components/layout/Sidebar'

interface BottomNavProps {
  activeView: ViewType
  onViewChange: (view: ViewType) => void
  className?: string
}

interface NavItem {
  id: ViewType
  label: string
  icon: React.ReactNode
}

// Standard mode navigation - simplified
const standardMainNavItems: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={22} /> },
  { id: 'overview', label: 'Dashboard', icon: <LayoutDashboard size={22} /> },
  { id: 'activity', label: 'Activity', icon: <Activity size={22} /> },
]

const standardMoreNavItems: NavItem[] = [
  { id: 'channels', label: 'Channels', icon: <Radio size={22} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={22} /> },
]

// Advanced mode navigation - full access
const advancedMainNavItems: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={22} /> },
  { id: 'overview', label: 'Dashboard', icon: <LayoutDashboard size={22} /> },
  { id: 'subagents', label: 'Agents', icon: <GitBranch size={22} /> },
]

const advancedMoreNavItems: NavItem[] = [
  { id: 'team', label: 'Team', icon: <UsersRound size={22} /> },
  { id: 'cron', label: 'Cron', icon: <Clock size={22} /> },
  { id: 'skills', label: 'Skills', icon: <Puzzle size={22} /> },
  { id: 'channels', label: 'Channels', icon: <Radio size={22} /> },
  { id: 'sessions', label: 'Sessions', icon: <Users size={22} /> },
  { id: 'logs', label: 'Logs', icon: <FileText size={22} /> },
  { id: 'config', label: 'Config', icon: <Code size={22} /> },
  { id: 'debug', label: 'Debug', icon: <Bug size={22} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={22} /> },
]

export function BottomNav({ activeView, onViewChange, className }: BottomNavProps) {
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const { userMode } = useUIStore()

  // Select navigation items based on user mode
  const mainNavItems = userMode === 'advanced' ? advancedMainNavItems : standardMainNavItems
  const moreNavItems = userMode === 'advanced' ? advancedMoreNavItems : standardMoreNavItems

  const isMoreActive = moreNavItems.some(item => item.id === activeView)

  const handleMoreClick = () => {
    setMoreMenuOpen(!moreMenuOpen)
  }

  const handleItemClick = (view: ViewType) => {
    onViewChange(view)
    setMoreMenuOpen(false)
  }

  return (
    <nav className={cn(
      'fixed bottom-0 left-0 right-0 z-50',
      'bg-sidebar-bg border-t border-sidebar-border',
      'safe-area-inset-bottom',
      className
    )}>
      {/* More Menu Popup */}
      {moreMenuOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setMoreMenuOpen(false)}
          />
          
          {/* Menu */}
          <div className="absolute bottom-full right-4 mb-2 z-50 bg-giga-card border border-sidebar-border rounded-xl shadow-xl overflow-hidden min-w-[160px] max-h-[60vh] overflow-y-auto">
            {moreNavItems.map((item) => (
              <button
                key={item.id}
                onClick={() => handleItemClick(item.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 transition-colors',
                  'hover:bg-giga-hover',
                  activeView === item.id
                    ? 'text-giga-accent bg-giga-hover'
                    : 'text-gray-300'
                )}
              >
                {item.icon}
                <span className="font-medium">{item.label}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {/* Main Nav */}
      <div className="flex items-center justify-around h-16 px-2">
        {mainNavItems.map((item) => (
          <button
            key={item.id}
            onClick={() => handleItemClick(item.id)}
            className={cn(
              'flex flex-col items-center justify-center gap-1 px-4 py-2 rounded-lg transition-all duration-200',
              'min-w-[64px]',
              activeView === item.id
                ? 'text-giga-accent'
                : 'text-gray-500 hover:text-gray-300'
            )}
          >
            <span className={cn(
              'transition-transform duration-200',
              activeView === item.id && 'scale-110'
            )}>
              {item.icon}
            </span>
            <span className="text-[10px] font-medium">{item.label}</span>
          </button>
        ))}

        {/* More Button */}
        <button
          onClick={handleMoreClick}
          className={cn(
            'flex flex-col items-center justify-center gap-1 px-4 py-2 rounded-lg transition-all duration-200',
            'min-w-[64px]',
            isMoreActive || moreMenuOpen
              ? 'text-giga-accent'
              : 'text-gray-500 hover:text-gray-300'
          )}
        >
          <span className={cn(
            'transition-transform duration-200',
            moreMenuOpen && 'rotate-90'
          )}>
            <MoreHorizontal size={22} />
          </span>
          <span className="text-[10px] font-medium">More</span>
        </button>
      </div>
    </nav>
  )
}
