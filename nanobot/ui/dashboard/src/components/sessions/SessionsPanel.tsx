import { useState } from 'react'
import { SessionTable } from './SessionTable'
import { SessionDetail } from './SessionDetail'
import { Search, Filter, RefreshCw } from 'lucide-react'
import { useSessions } from '@/hooks/useSessions'
import { cn } from '@/lib/utils'

export function SessionsPanel() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSessionKey, setSelectedSessionKey] = useState<string | null>(null)
  const { refetch, isRefetching } = useSessions()

  return (
    <div className="flex h-full">
      {/* Main Table Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="p-6 border-b border-sidebar-border">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Sessions</h1>
              <p className="text-sm text-gray-500 mt-1">
                Manage active and historical chat sessions
              </p>
            </div>

            <div className="flex items-center gap-2">
              {/* Search */}
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search sessions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-64 pl-9 pr-3 py-2 bg-giga-card border border-sidebar-border rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-giga-accent transition-colors"
                />
              </div>

              {/* Filter */}
              <button className="p-2 rounded-lg bg-giga-card border border-sidebar-border text-gray-400 hover:text-white hover:border-giga-accent transition-colors">
                <Filter size={18} />
              </button>

              {/* Refresh */}
              <button 
                onClick={() => refetch()}
                disabled={isRefetching}
                className="p-2 rounded-lg bg-giga-card border border-sidebar-border text-gray-400 hover:text-white hover:border-giga-accent transition-colors disabled:opacity-50"
              >
                <RefreshCw size={18} className={cn(isRefetching && 'animate-spin')} />
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-hidden">
          <SessionTable 
            searchQuery={searchQuery}
            onSelectSession={setSelectedSessionKey}
            selectedKey={selectedSessionKey}
          />
        </div>
      </div>

      {/* Detail Panel - Desktop only */}
      {selectedSessionKey && (
        <div className="hidden xl:flex w-96 border-l border-sidebar-border flex-col">
          <SessionDetail 
            sessionKey={selectedSessionKey}
            onClose={() => setSelectedSessionKey(null)}
          />
        </div>
      )}
    </div>
  )
}
