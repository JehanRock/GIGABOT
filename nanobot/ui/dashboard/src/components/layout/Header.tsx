import { useState } from 'react'
import { 
  Search, 
  Menu, 
  X,
  Wifi,
  WifiOff,
  Loader2,
  Moon,
  Sun,
  RefreshCw
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { NotificationCenter } from './NotificationCenter'
import { UserModeToggleCompact } from '@/components/settings/UserModeToggle'

export function Header() {
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { 
    connectionStatus, 
    theme, 
    toggleTheme,
    mobileMenuOpen,
    setMobileMenuOpen 
  } = useUIStore()

  const { data: status, refetch: refetchStatus, isRefetching } = useQuery({
    queryKey: ['status'],
    queryFn: () => api.getStatus(),
    refetchInterval: 30000, // Refetch every 30 seconds
  })

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return <Wifi size={16} className="text-giga-success" />
      case 'connecting':
        return <Loader2 size={16} className="text-giga-warning animate-spin" />
      case 'disconnected':
        return <WifiOff size={16} className="text-giga-error" />
    }
  }

  const getConnectionText = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected'
      case 'connecting':
        return 'Connecting...'
      case 'disconnected':
        return 'Disconnected'
    }
  }

  return (
    <header className="h-16 border-b border-sidebar-border bg-giga-darker/50 backdrop-blur-sm flex items-center justify-between px-4 gap-4">
      {/* Mobile Menu Button */}
      <button
        className="md:hidden p-2 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
      >
        {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Search */}
      <div className={cn(
        'flex-1 max-w-md transition-all duration-200',
        searchOpen ? 'opacity-100' : 'opacity-100 md:opacity-100'
      )}>
        <div className="relative">
          <Search 
            size={18} 
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" 
          />
          <input
            type="text"
            placeholder="Search conversations, sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-giga-card border border-sidebar-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-giga-accent focus:ring-1 focus:ring-giga-accent transition-colors"
          />
        </div>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-2">
        {/* Connection Status */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-giga-card border border-sidebar-border">
          {getConnectionIcon()}
          <span className="text-sm text-gray-400">{getConnectionText()}</span>
        </div>

        {/* Model Badge */}
        {status?.model && (
          <div className="hidden lg:flex items-center px-3 py-1.5 rounded-lg bg-giga-accent/10 border border-giga-accent/20">
            <span className="text-sm text-giga-accent font-medium truncate max-w-[150px]">
              {status.model}
            </span>
          </div>
        )}

        {/* Refresh Button */}
        <button
          onClick={() => refetchStatus()}
          disabled={isRefetching}
          className="p-2 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors disabled:opacity-50"
          title="Refresh status"
        >
          <RefreshCw size={18} className={cn(isRefetching && 'animate-spin')} />
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Notifications */}
        <NotificationCenter />

        {/* Mode Toggle - Mobile only (desktop has it in sidebar) */}
        <div className="hidden sm:block md:hidden">
          <UserModeToggleCompact />
        </div>

        {/* User Avatar */}
        <button className="w-8 h-8 rounded-full bg-gradient-to-br from-giga-accent to-purple-500 flex items-center justify-center text-white text-sm font-bold">
          U
        </button>
      </div>
    </header>
  )
}
