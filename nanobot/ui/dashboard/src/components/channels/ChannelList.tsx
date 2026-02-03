import { 
  MessageCircle,
  Send,
  Hash,
  Slack,
  Shield,
  Globe,
  Smartphone,
  Settings,
  QrCode,
  Power,
  PowerOff
} from 'lucide-react'
import { useChannels } from '@/hooks/useChannels'
import { cn, getChannelColor } from '@/lib/utils'
import type { ChannelType, ChannelStatus } from '@/types'

interface ChannelListProps {
  onSelectChannel: (channel: ChannelType) => void
  onQRLogin: (channel: ChannelType) => void
  selectedChannel: ChannelType | null
}

interface ChannelInfo {
  type: ChannelType
  name: string
  icon: React.ReactNode
  description: string
  supportsQR: boolean
}

const channelInfoMap: ChannelInfo[] = [
  {
    type: 'whatsapp',
    name: 'WhatsApp',
    icon: <MessageCircle size={24} />,
    description: 'Connect via WhatsApp Business API or QR code',
    supportsQR: true,
  },
  {
    type: 'telegram',
    name: 'Telegram',
    icon: <Send size={24} />,
    description: 'Connect via Telegram Bot API',
    supportsQR: false,
  },
  {
    type: 'discord',
    name: 'Discord',
    icon: <Hash size={24} />,
    description: 'Connect via Discord Bot',
    supportsQR: false,
  },
  {
    type: 'slack',
    name: 'Slack',
    icon: <Slack size={24} />,
    description: 'Connect via Slack App',
    supportsQR: false,
  },
  {
    type: 'signal',
    name: 'Signal',
    icon: <Shield size={24} />,
    description: 'Connect via Signal CLI',
    supportsQR: true,
  },
  {
    type: 'matrix',
    name: 'Matrix',
    icon: <Globe size={24} />,
    description: 'Connect via Matrix protocol',
    supportsQR: false,
  },
  {
    type: 'sms',
    name: 'SMS',
    icon: <Smartphone size={24} />,
    description: 'Connect via Twilio or similar',
    supportsQR: false,
  },
]

export function ChannelList({ onSelectChannel, onQRLogin, selectedChannel }: ChannelListProps) {
  const { data, isLoading } = useChannels()
  
  const channelStatuses = data?.channels || {}

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="card animate-pulse">
            <div className="h-12 w-12 bg-giga-hover rounded-xl mb-4" />
            <div className="h-4 w-24 bg-giga-hover rounded mb-2" />
            <div className="h-3 w-32 bg-giga-hover rounded" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {channelInfoMap.map((info) => (
        <ChannelCard
          key={info.type}
          info={info}
          status={channelStatuses[info.type]}
          isSelected={selectedChannel === info.type}
          onSelect={() => onSelectChannel(info.type)}
          onQRLogin={() => onQRLogin(info.type)}
        />
      ))}
    </div>
  )
}

interface ChannelCardProps {
  info: ChannelInfo
  status?: ChannelStatus
  isSelected: boolean
  onSelect: () => void
  onQRLogin: () => void
}

function ChannelCard({ info, status, isSelected, onSelect, onQRLogin }: ChannelCardProps) {
  const isEnabled = status?.enabled
  const isRunning = status?.running
  const hasError = status?.error

  return (
    <div 
      className={cn(
        'card cursor-pointer transition-all duration-200',
        'hover:border-giga-accent/50',
        isSelected && 'border-giga-accent ring-1 ring-giga-accent'
      )}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div 
          className="w-12 h-12 rounded-xl flex items-center justify-center text-white"
          style={{ backgroundColor: getChannelColor(info.type) }}
        >
          {info.icon}
        </div>
        
        {/* Status Badge */}
        <div className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium',
          isRunning 
            ? 'bg-giga-success/20 text-giga-success' 
            : isEnabled
            ? 'bg-giga-warning/20 text-giga-warning'
            : 'bg-gray-500/20 text-gray-500'
        )}>
          {isRunning ? (
            <>
              <Power size={12} />
              Online
            </>
          ) : isEnabled ? (
            <>
              <PowerOff size={12} />
              Disconnected
            </>
          ) : (
            <>
              <PowerOff size={12} />
              Disabled
            </>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="mb-4">
        <h3 className="font-semibold text-white mb-1">{info.name}</h3>
        <p className="text-xs text-gray-500">{info.description}</p>
      </div>

      {/* Error */}
      {hasError && (
        <div className="mb-4 p-2 bg-giga-error/10 border border-giga-error/20 rounded-lg">
          <p className="text-xs text-giga-error truncate">{status?.error}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-4 border-t border-sidebar-border">
        <button 
          onClick={(e) => {
            e.stopPropagation()
            onSelect()
          }}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-giga-hover rounded-lg text-sm text-gray-300 hover:text-white transition-colors"
        >
          <Settings size={14} />
          Configure
        </button>
        
        {info.supportsQR && !isRunning && (
          <button 
            onClick={(e) => {
              e.stopPropagation()
              onQRLogin()
            }}
            className="flex items-center justify-center gap-2 px-3 py-2 bg-giga-accent/20 rounded-lg text-sm text-giga-accent hover:bg-giga-accent/30 transition-colors"
          >
            <QrCode size={14} />
            QR Login
          </button>
        )}
      </div>
    </div>
  )
}
