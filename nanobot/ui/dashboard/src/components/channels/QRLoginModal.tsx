import { useState, useEffect } from 'react'
import { X, RefreshCw, CheckCircle, Loader2 } from 'lucide-react'
import { getChannelColor, cn } from '@/lib/utils'
import type { ChannelType } from '@/types'

interface QRLoginModalProps {
  channel: ChannelType
  onClose: () => void
}

type QRStatus = 'loading' | 'ready' | 'scanning' | 'success' | 'error'

export function QRLoginModal({ channel, onClose }: QRLoginModalProps) {
  const [status, setStatus] = useState<QRStatus>('loading')
  const [qrCode, setQRCode] = useState<string | null>(null)

  // Simulate QR code generation
  useEffect(() => {
    const timer = setTimeout(() => {
      setStatus('ready')
      // In production, this would be a real QR code from the API
      setQRCode('data:image/svg+xml,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
          <rect fill="white" width="200" height="200"/>
          <text x="100" y="100" text-anchor="middle" fill="#1a1a2e" font-size="14">QR Code</text>
          <text x="100" y="120" text-anchor="middle" fill="#666" font-size="10">Placeholder</text>
        </svg>
      `))
    }, 1500)

    return () => clearTimeout(timer)
  }, [])

  const handleRefresh = () => {
    setStatus('loading')
    setQRCode(null)
    setTimeout(() => {
      setStatus('ready')
    }, 1500)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-giga-card border border-sidebar-border rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
          <div className="flex items-center gap-3">
            <div 
              className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-sm font-bold"
              style={{ backgroundColor: getChannelColor(channel) }}
            >
              {channel.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="font-semibold text-white capitalize">{channel} Login</h2>
              <p className="text-xs text-gray-500">Scan QR code to connect</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-giga-hover text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* QR Code Area */}
          <div className="relative aspect-square bg-white rounded-xl overflow-hidden mb-6">
            {status === 'loading' && (
              <div className="absolute inset-0 flex items-center justify-center bg-giga-card">
                <Loader2 size={32} className="text-giga-accent animate-spin" />
              </div>
            )}
            
            {status === 'ready' && qrCode && (
              <img 
                src={qrCode} 
                alt="QR Code" 
                className="w-full h-full object-contain p-4"
              />
            )}
            
            {status === 'scanning' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-giga-card/90">
                <Loader2 size={32} className="text-giga-accent animate-spin mb-2" />
                <p className="text-sm text-white">Scanning...</p>
              </div>
            )}
            
            {status === 'success' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-giga-success/10">
                <CheckCircle size={48} className="text-giga-success mb-2" />
                <p className="text-sm text-white">Connected!</p>
              </div>
            )}
            
            {status === 'error' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-giga-error/10">
                <X size={48} className="text-giga-error mb-2" />
                <p className="text-sm text-white">Failed to connect</p>
              </div>
            )}
          </div>

          {/* Instructions */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-medium text-white">Instructions</h3>
            <ol className="space-y-2 text-sm text-gray-400">
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-giga-accent/20 text-giga-accent text-xs flex items-center justify-center">
                  1
                </span>
                Open {channel} on your phone
              </li>
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-giga-accent/20 text-giga-accent text-xs flex items-center justify-center">
                  2
                </span>
                Go to Settings → Linked Devices
              </li>
              <li className="flex items-start gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-giga-accent/20 text-giga-accent text-xs flex items-center justify-center">
                  3
                </span>
                Tap "Link a Device" and scan this code
              </li>
            </ol>
          </div>

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={status === 'loading'}
            className={cn(
              'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-colors',
              'bg-giga-hover text-gray-300 hover:text-white',
              status === 'loading' && 'opacity-50 cursor-not-allowed'
            )}
          >
            <RefreshCw size={18} className={cn(status === 'loading' && 'animate-spin')} />
            <span className="text-sm font-medium">Refresh QR Code</span>
          </button>
        </div>
      </div>
    </div>
  )
}
