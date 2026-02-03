import { useState } from 'react'
import { ChannelList } from './ChannelList'
import { ChannelConfig } from './ChannelConfig'
import { QRLoginModal } from './QRLoginModal'
import { QuickConnectWizard } from './QuickConnectWizard'
import { RefreshCw, Plus, Wand2 } from 'lucide-react'
import { useChannels } from '@/hooks/useChannels'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import type { ChannelType } from '@/types'

export function ChannelsPanel() {
  const [selectedChannel, setSelectedChannel] = useState<ChannelType | null>(null)
  const [qrModalChannel, setQRModalChannel] = useState<ChannelType | null>(null)
  const [showWizard, setShowWizard] = useState(false)
  const { refetch, isRefetching } = useChannels()
  const { userMode } = useUIStore()
  const isStandard = userMode === 'standard'

  const handleWizardComplete = (channelId: string, config: Record<string, string>) => {
    console.log('Channel connected:', channelId, config)
    refetch()
  }

  return (
    <div className="flex h-full">
      {/* Main List Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="p-6 border-b border-sidebar-border">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Channels</h1>
              <p className="text-sm text-gray-500 mt-1">
                {isStandard 
                  ? 'Connect your messaging apps'
                  : 'Manage messaging platform integrations'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              {/* Quick Connect Wizard (Standard mode primary action) */}
              {isStandard ? (
                <button 
                  onClick={() => setShowWizard(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-giga-accent hover:bg-giga-accent-hover text-white rounded-lg transition-colors"
                >
                  <Wand2 size={18} />
                  <span className="text-sm font-medium">Connect Channel</span>
                </button>
              ) : (
                <button 
                  onClick={() => setShowWizard(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-giga-accent hover:bg-giga-accent-hover text-white rounded-lg transition-colors"
                >
                  <Plus size={18} />
                  <span className="text-sm font-medium">Add Channel</span>
                </button>
              )}

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

        {/* Channel List */}
        <div className="flex-1 overflow-y-auto p-6">
          <ChannelList 
            onSelectChannel={setSelectedChannel}
            onQRLogin={setQRModalChannel}
            selectedChannel={selectedChannel}
          />
        </div>
      </div>

      {/* Config Panel - Desktop only, Advanced mode only */}
      {selectedChannel && !isStandard && (
        <div className="hidden xl:flex w-96 border-l border-sidebar-border flex-col">
          <ChannelConfig 
            channel={selectedChannel}
            onClose={() => setSelectedChannel(null)}
          />
        </div>
      )}

      {/* QR Login Modal */}
      {qrModalChannel && (
        <QRLoginModal 
          channel={qrModalChannel}
          onClose={() => setQRModalChannel(null)}
        />
      )}

      {/* Quick Connect Wizard */}
      <QuickConnectWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onComplete={handleWizardComplete}
      />
    </div>
  )
}
