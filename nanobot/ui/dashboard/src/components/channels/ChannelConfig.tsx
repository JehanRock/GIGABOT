import { useState } from 'react'
import { X, Save, Power, PowerOff, Trash2 } from 'lucide-react'
import { useChannels } from '@/hooks/useChannels'
import { getChannelColor, getChannelInitials, cn } from '@/lib/utils'
import type { ChannelType } from '@/types'

interface ChannelConfigProps {
  channel: ChannelType
  onClose: () => void
}

export function ChannelConfig({ channel, onClose }: ChannelConfigProps) {
  const { data } = useChannels()
  const status = data?.channels?.[channel]
  
  const [config, setConfig] = useState({
    enabled: status?.enabled || false,
    // Add more config fields as needed
  })

  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    // TODO: Implement save via API
    await new Promise(resolve => setTimeout(resolve, 1000))
    setIsSaving(false)
  }

  const handleToggle = () => {
    setConfig(prev => ({ ...prev, enabled: !prev.enabled }))
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div 
            className="w-10 h-10 rounded-xl flex items-center justify-center text-white"
            style={{ backgroundColor: getChannelColor(channel) }}
          >
            {getChannelInitials(channel)}
          </div>
          <div>
            <h3 className="font-semibold text-white capitalize">{channel}</h3>
            <p className="text-xs text-gray-500">Configuration</p>
          </div>
        </div>
        <button 
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 bg-giga-card rounded-lg border border-sidebar-border">
          <div>
            <p className="font-medium text-white">Channel Status</p>
            <p className="text-xs text-gray-500">
              {config.enabled ? 'Channel is enabled' : 'Channel is disabled'}
            </p>
          </div>
          <button
            onClick={handleToggle}
            className={cn(
              'relative w-12 h-6 rounded-full transition-colors',
              config.enabled ? 'bg-giga-success' : 'bg-gray-600'
            )}
          >
            <span
              className={cn(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                config.enabled ? 'left-7' : 'left-1'
              )}
            />
          </button>
        </div>

        {/* Connection Status */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Connection
          </h4>
          <div className={cn(
            'p-4 rounded-lg border flex items-center justify-between',
            status?.running 
              ? 'bg-giga-success/10 border-giga-success/20'
              : 'bg-giga-card border-sidebar-border'
          )}>
            <div className="flex items-center gap-3">
              {status?.running ? (
                <Power size={20} className="text-giga-success" />
              ) : (
                <PowerOff size={20} className="text-gray-500" />
              )}
              <div>
                <p className="text-sm font-medium text-white">
                  {status?.running ? 'Connected' : 'Disconnected'}
                </p>
                <p className="text-xs text-gray-500">
                  {status?.running ? 'Receiving messages' : 'Not receiving messages'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Configuration Fields */}
        <div className="space-y-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Settings
          </h4>

          {/* Placeholder config fields - would be dynamic based on channel type */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API Token
              </label>
              <input
                type="password"
                placeholder="Enter API token..."
                className="input"
              />
              <p className="text-xs text-gray-600 mt-1">
                Your {channel} API token or bot token
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Webhook URL
              </label>
              <input
                type="text"
                placeholder="https://..."
                className="input"
                readOnly
                value={`https://your-domain.com/webhook/${channel}`}
              />
              <p className="text-xs text-gray-600 mt-1">
                Configure this URL in your {channel} settings
              </p>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="space-y-2 pt-4 border-t border-sidebar-border">
          <h4 className="text-xs font-semibold text-giga-error uppercase tracking-wider">
            Danger Zone
          </h4>
          <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-giga-error/10 border border-giga-error/20 rounded-lg text-giga-error hover:bg-giga-error/20 transition-colors">
            <Trash2 size={18} />
            <span className="text-sm font-medium">Remove Channel</span>
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-sidebar-border">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-giga-accent hover:bg-giga-accent-hover rounded-lg text-white transition-colors disabled:opacity-50"
        >
          <Save size={18} />
          <span className="text-sm font-medium">
            {isSaving ? 'Saving...' : 'Save Changes'}
          </span>
        </button>
      </div>
    </div>
  )
}
