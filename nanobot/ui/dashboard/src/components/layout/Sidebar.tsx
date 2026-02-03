import { 
  MessageSquare, 
  LayoutDashboard, 
  Radio, 
  Users, 
  Settings, 
  ChevronLeft,
  ChevronRight,
  Zap,
  Bot,
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
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import { UserModeToggleCompact } from '@/components/settings/UserModeToggle'

export type ViewType = 
  | 'chat' | 'overview' | 'channels' | 'sessions' | 'settings'  // Existing
  | 'activity' | 'subagents' | 'team' | 'cron' | 'skills'       // New
  | 'nodes' | 'logs' | 'config' | 'debug'                       // New

interface SidebarProps {
  activeView: ViewType
  onViewChange: (view: ViewType) => void
  className?: string
}

interface NavItem {
  id: ViewType
  label: string
  icon: React.ReactNode
  badge?: number
  advancedOnly?: boolean
  standardOnly?: boolean
}

// Standard mode navigation items
const standardNavItems: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={20} /> },
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={20} /> },
  { id: 'activity', label: 'Activity', icon: <Activity size={20} />, standardOnly: true },
  { id: 'channels', label: 'Channels', icon: <Radio size={20} /> },
]

// Advanced mode navigation items (includes everything)
const advancedNavItems: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={20} /> },
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={20} /> },
  { id: 'subagents', label: 'Sub-Agents', icon: <GitBranch size={20} />, advancedOnly: true },
  { id: 'team', label: 'Team/Swarm', icon: <UsersRound size={20} />, advancedOnly: true },
  { id: 'cron', label: 'Cron Jobs', icon: <Clock size={20} />, advancedOnly: true },
  { id: 'skills', label: 'Skills', icon: <Puzzle size={20} />, advancedOnly: true },
  { id: 'channels', label: 'Channels', icon: <Radio size={20} /> },
  { id: 'sessions', label: 'Sessions', icon: <Users size={20} /> },
  { id: 'nodes', label: 'Nodes', icon: <Network size={20} />, advancedOnly: true },
  { id: 'logs', label: 'Logs', icon: <FileText size={20} />, advancedOnly: true },
  { id: 'config', label: 'Config', icon: <Code size={20} />, advancedOnly: true },
  { id: 'debug', label: 'Debug', icon: <Bug size={20} />, advancedOnly: true },
]

const bottomNavItems: NavItem[] = [
  { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
]

export function Sidebar({ activeView, onViewChange, className }: SidebarProps) {
  const { sidebarCollapsed, toggleSidebar, userMode } = useUIStore()

  // Select navigation items based on user mode
  const navItems = userMode === 'advanced' ? advancedNavItems : standardNavItems

  return (
    <aside
      className={cn(
        'flex flex-col bg-sidebar-bg border-r border-sidebar-border transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64',
        className
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 p-4 border-b border-sidebar-border">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-giga-accent to-purple-500 flex items-center justify-center flex-shrink-0">
          <Bot size={24} className="text-white" />
        </div>
        {!sidebarCollapsed && (
          <div className="overflow-hidden flex-1">
            <h1 className="font-bold text-lg text-white truncate">GigaBot</h1>
            <p className="text-xs text-gray-500 truncate">Dashboard</p>
          </div>
        )}
      </div>

      {/* Mode Toggle - when sidebar expanded */}
      {!sidebarCollapsed && (
        <div className="px-3 py-2 border-b border-sidebar-border">
          <UserModeToggleCompact className="w-full justify-center" />
        </div>
      )}

      {/* Main Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="mb-4">
          {!sidebarCollapsed && (
            <p className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {userMode === 'advanced' ? 'Navigation' : 'Main'}
            </p>
          )}
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                'hover:bg-sidebar-hover',
                activeView === item.id
                  ? 'bg-sidebar-active text-white'
                  : 'text-gray-400 hover:text-white',
                sidebarCollapsed && 'justify-center'
              )}
              title={sidebarCollapsed ? item.label : undefined}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!sidebarCollapsed && (
                <>
                  <span className="flex-1 text-left text-sm font-medium">
                    {item.label}
                  </span>
                  {item.badge && item.badge > 0 && (
                    <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-giga-accent text-white">
                      {item.badge}
                    </span>
                  )}
                  {item.advancedOnly && (
                    <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-purple-500/20 text-purple-400">
                      ADV
                    </span>
                  )}
                </>
              )}
            </button>
          ))}
        </div>

        {/* Status Section */}
        {!sidebarCollapsed && (
          <div className="mb-4">
            <p className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Status
            </p>
            <div className="px-3 py-2 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <Zap size={14} className="text-giga-success" />
                <span>System Online</span>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Bottom Navigation */}
      <div className="p-3 border-t border-sidebar-border">
        {bottomNavItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
              'hover:bg-sidebar-hover',
              activeView === item.id
                ? 'bg-sidebar-active text-white'
                : 'text-gray-400 hover:text-white',
              sidebarCollapsed && 'justify-center'
            )}
            title={sidebarCollapsed ? item.label : undefined}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!sidebarCollapsed && (
              <span className="flex-1 text-left text-sm font-medium">
                {item.label}
              </span>
            )}
          </button>
        ))}

        {/* Collapse Toggle */}
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center gap-3 px-3 py-2.5 mt-2 rounded-lg text-gray-400 hover:text-white hover:bg-sidebar-hover transition-all duration-200"
          title={sidebarCollapsed ? 'Expand' : 'Collapse'}
        >
          {sidebarCollapsed ? (
            <ChevronRight size={20} />
          ) : (
            <>
              <ChevronLeft size={20} />
              <span className="text-sm">Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
