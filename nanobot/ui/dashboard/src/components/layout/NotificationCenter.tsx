import { useState, useRef, useEffect } from 'react'
import { Bell, Check, CheckCheck, X, AlertTriangle, CheckCircle, Info, Clock, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  timestamp: string
  read: boolean
  actionUrl?: string
}

// Mock notifications - TODO: Replace with real API/WebSocket
const mockNotifications: Notification[] = [
  {
    id: 'n1',
    type: 'success',
    title: 'Task completed',
    message: 'Research task "TypeScript best practices" has been completed successfully.',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    read: false,
    actionUrl: '/activity',
  },
  {
    id: 'n2',
    type: 'warning',
    title: 'Rate limit approaching',
    message: 'OpenAI API usage at 80% of daily limit.',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    read: false,
  },
  {
    id: 'n3',
    type: 'info',
    title: 'Scheduled task running',
    message: 'Daily summary generation started.',
    timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    read: true,
  },
  {
    id: 'n4',
    type: 'error',
    title: 'Channel disconnected',
    message: 'WhatsApp connection lost. Reconnecting...',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    read: true,
    actionUrl: '/channels',
  },
]

function NotificationItem({ 
  notification, 
  onMarkRead,
  onDismiss 
}: { 
  notification: Notification
  onMarkRead: () => void
  onDismiss: () => void
}) {
  const getIcon = () => {
    switch (notification.type) {
      case 'success':
        return <CheckCircle size={16} className="text-giga-success" />
      case 'error':
        return <AlertTriangle size={16} className="text-giga-error" />
      case 'warning':
        return <AlertTriangle size={16} className="text-giga-warning" />
      case 'info':
        return <Info size={16} className="text-blue-400" />
    }
  }

  const getTimeAgo = (timestamp: string) => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000)
    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  return (
    <div className={cn(
      'p-3 border-b border-giga-border hover:bg-giga-hover/50 transition-colors',
      !notification.read && 'bg-giga-accent/5'
    )}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{getIcon()}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className={cn(
              'text-sm font-medium truncate',
              notification.read ? 'text-gray-300' : 'text-white'
            )}>
              {notification.title}
            </h4>
            <span className="text-[10px] text-gray-500 flex-shrink-0">
              {getTimeAgo(notification.timestamp)}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{notification.message}</p>
          <div className="flex items-center gap-2 mt-2">
            {!notification.read && (
              <button 
                onClick={onMarkRead}
                className="text-[10px] text-giga-accent hover:text-giga-accent-hover transition-colors"
              >
                Mark read
              </button>
            )}
            {notification.actionUrl && (
              <a 
                href={notification.actionUrl}
                className="text-[10px] text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
              >
                View <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
        <button 
          onClick={onDismiss}
          className="p-1 rounded text-gray-500 hover:text-white hover:bg-giga-hover transition-colors"
        >
          <X size={12} />
        </button>
      </div>
    </div>
  )
}

export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState(mockNotifications)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const unreadCount = notifications.filter(n => !n.read).length

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleMarkRead = (id: string) => {
    setNotifications(prev => 
      prev.map(n => n.id === id ? { ...n, read: true } : n)
    )
  }

  const handleMarkAllRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const handleDismiss = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  const handleClearAll = () => {
    setNotifications([])
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'relative p-2 rounded-lg transition-colors',
          isOpen 
            ? 'bg-giga-accent/20 text-giga-accent'
            : 'text-gray-400 hover:text-white hover:bg-giga-hover'
        )}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center text-[10px] font-bold bg-giga-error text-white rounded-full">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-giga-card border border-giga-border rounded-xl shadow-xl overflow-hidden z-50">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-giga-border">
            <h3 className="font-medium text-white">Notifications</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button 
                  onClick={handleMarkAllRead}
                  className="text-xs text-giga-accent hover:text-giga-accent-hover transition-colors flex items-center gap-1"
                >
                  <CheckCheck size={12} />
                  Mark all read
                </button>
              )}
            </div>
          </div>

          {/* Notification List */}
          <div className="max-h-80 overflow-y-auto">
            {notifications.length > 0 ? (
              notifications.map(notification => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onMarkRead={() => handleMarkRead(notification.id)}
                  onDismiss={() => handleDismiss(notification.id)}
                />
              ))
            ) : (
              <div className="p-8 text-center">
                <Bell size={32} className="mx-auto text-gray-600 mb-2" />
                <p className="text-sm text-gray-400">No notifications</p>
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="flex items-center justify-between p-3 border-t border-giga-border bg-giga-dark/50">
              <a 
                href="/activity" 
                className="text-xs text-gray-400 hover:text-white transition-colors"
              >
                View all activity
              </a>
              <button 
                onClick={handleClearAll}
                className="text-xs text-gray-500 hover:text-giga-error transition-colors"
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
