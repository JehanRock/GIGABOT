import { useState } from 'react'
import { Radio, MessageCircle, Send, Hash, Phone, ChevronRight, ChevronLeft, Check, X, QrCode, Key, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChannelType {
  id: string
  name: string
  icon: React.ReactNode
  description: string
  setupMethod: 'qr' | 'token' | 'oauth'
  color: string
}

const channelTypes: ChannelType[] = [
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    icon: <Phone size={24} />,
    description: 'Connect via QR code scan',
    setupMethod: 'qr',
    color: 'bg-green-500/20 text-green-400 border-green-500/30',
  },
  {
    id: 'telegram',
    name: 'Telegram',
    icon: <Send size={24} />,
    description: 'Connect with bot token',
    setupMethod: 'token',
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  {
    id: 'discord',
    name: 'Discord',
    icon: <Hash size={24} />,
    description: 'Connect with bot token',
    setupMethod: 'token',
    color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  },
  {
    id: 'slack',
    name: 'Slack',
    icon: <MessageCircle size={24} />,
    description: 'Connect with OAuth',
    setupMethod: 'oauth',
    color: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  },
]

type WizardStep = 'select' | 'configure' | 'confirm'

interface QuickConnectWizardProps {
  isOpen: boolean
  onClose: () => void
  onComplete: (channelId: string, config: Record<string, string>) => void
}

export function QuickConnectWizard({ isOpen, onClose, onComplete }: QuickConnectWizardProps) {
  const [step, setStep] = useState<WizardStep>('select')
  const [selectedChannel, setSelectedChannel] = useState<ChannelType | null>(null)
  const [token, setToken] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSelectChannel = (channel: ChannelType) => {
    setSelectedChannel(channel)
    setStep('configure')
    setError(null)
  }

  const handleBack = () => {
    if (step === 'configure') {
      setStep('select')
      setSelectedChannel(null)
      setToken('')
    } else if (step === 'confirm') {
      setStep('configure')
    }
  }

  const handleConnect = async () => {
    if (!selectedChannel) return
    
    setConnecting(true)
    setError(null)

    // Mock connection - TODO: Replace with real API
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    // Simulate success/failure
    const success = Math.random() > 0.3
    
    if (success) {
      setStep('confirm')
    } else {
      setError('Connection failed. Please check your credentials and try again.')
    }
    
    setConnecting(false)
  }

  const handleComplete = () => {
    if (selectedChannel) {
      onComplete(selectedChannel.id, { token })
    }
    handleReset()
    onClose()
  }

  const handleReset = () => {
    setStep('select')
    setSelectedChannel(null)
    setToken('')
    setError(null)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-giga-card border border-giga-border rounded-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-giga-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-giga-accent/20 flex items-center justify-center">
              <Radio size={20} className="text-giga-accent" />
            </div>
            <div>
              <h3 className="font-bold text-white">Connect Channel</h3>
              <p className="text-xs text-gray-500">Quick setup wizard</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-2 px-4 py-3 bg-giga-dark/50">
          {(['select', 'configure', 'confirm'] as const).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={cn(
                'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors',
                step === s || (['configure', 'confirm'].includes(step) && s === 'select') || (step === 'confirm' && s === 'configure')
                  ? 'bg-giga-accent text-white'
                  : 'bg-giga-border text-gray-500'
              )}>
                {(step === 'confirm' && s !== 'confirm') || (step === 'configure' && s === 'select') ? (
                  <Check size={14} />
                ) : (
                  i + 1
                )}
              </div>
              {i < 2 && (
                <div className={cn(
                  'w-12 h-0.5 rounded-full transition-colors',
                  (['configure', 'confirm'].includes(step) && s === 'select') || (step === 'confirm' && s === 'configure')
                    ? 'bg-giga-accent'
                    : 'bg-giga-border'
                )} />
              )}
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="p-4">
          {step === 'select' && (
            <div className="space-y-3">
              <p className="text-sm text-gray-400 mb-4">Select the channel you want to connect:</p>
              {channelTypes.map((channel) => (
                <button
                  key={channel.id}
                  onClick={() => handleSelectChannel(channel)}
                  className={cn(
                    'w-full flex items-center gap-4 p-4 rounded-lg border transition-all',
                    'hover:bg-giga-hover',
                    channel.color.replace('bg-', 'border-').split(' ')[0] + '/20',
                    'border-giga-border hover:border-giga-accent'
                  )}
                >
                  <div className={cn('w-12 h-12 rounded-lg flex items-center justify-center border', channel.color)}>
                    {channel.icon}
                  </div>
                  <div className="flex-1 text-left">
                    <h4 className="font-medium text-white">{channel.name}</h4>
                    <p className="text-sm text-gray-400">{channel.description}</p>
                  </div>
                  <ChevronRight size={20} className="text-gray-500" />
                </button>
              ))}
            </div>
          )}

          {step === 'configure' && selectedChannel && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 mb-4">
                <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border', selectedChannel.color)}>
                  {selectedChannel.icon}
                </div>
                <div>
                  <h4 className="font-medium text-white">{selectedChannel.name}</h4>
                  <p className="text-xs text-gray-500">{selectedChannel.description}</p>
                </div>
              </div>

              {selectedChannel.setupMethod === 'qr' ? (
                <div className="text-center py-8">
                  <div className="w-48 h-48 mx-auto bg-white rounded-xl p-4 mb-4">
                    <QrCode size={160} className="text-gray-800" />
                  </div>
                  <p className="text-sm text-gray-400">
                    Scan this QR code with your WhatsApp app
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    Go to WhatsApp &gt; Settings &gt; Linked Devices &gt; Link a Device
                  </p>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    {selectedChannel.id === 'telegram' ? 'Bot Token' : 'Bot Token / API Key'}
                  </label>
                  <div className="relative">
                    <Key size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      type="password"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none"
                      placeholder="Enter your bot token..."
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    {selectedChannel.id === 'telegram' && 'Get your token from @BotFather on Telegram'}
                    {selectedChannel.id === 'discord' && 'Get your token from the Discord Developer Portal'}
                    {selectedChannel.id === 'slack' && 'Get your token from the Slack API dashboard'}
                  </p>
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-giga-error/20 text-giga-error text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
            </div>
          )}

          {step === 'confirm' && selectedChannel && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-giga-success/20 flex items-center justify-center mb-4">
                <Check size={32} className="text-giga-success" />
              </div>
              <h4 className="text-lg font-bold text-white mb-2">Connection Successful!</h4>
              <p className="text-sm text-gray-400">
                Your {selectedChannel.name} channel is now connected to GigaBot.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-giga-border">
          <button
            onClick={handleBack}
            disabled={step === 'select'}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
              step === 'select'
                ? 'text-gray-600 cursor-not-allowed'
                : 'text-gray-400 hover:text-white hover:bg-giga-hover'
            )}
          >
            <ChevronLeft size={16} />
            <span>Back</span>
          </button>
          
          {step === 'configure' && (
            <button
              onClick={handleConnect}
              disabled={connecting || (selectedChannel?.setupMethod !== 'qr' && !token)}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              {connecting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Connecting...</span>
                </>
              ) : (
                <>
                  <span>Connect</span>
                  <ChevronRight size={16} />
                </>
              )}
            </button>
          )}
          
          {step === 'confirm' && (
            <button onClick={handleComplete} className="btn-primary">
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
