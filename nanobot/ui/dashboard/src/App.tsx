import { useState, useEffect } from 'react'
import { Sidebar, ViewType } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { BottomNav } from '@/components/layout/BottomNav'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { OverviewPanel } from '@/components/overview/OverviewPanel'
import { ChannelsPanel } from '@/components/channels/ChannelsPanel'
import { SessionsPanel } from '@/components/sessions/SessionsPanel'
import { SettingsPanel } from '@/components/settings/SettingsPanel'
import { ActivityPanel } from '@/components/activity/ActivityPanel'
import { SubAgentsPanel } from '@/components/subagents/SubAgentsPanel'
import { TeamPanel } from '@/components/team/TeamPanel'
import { CronPanel } from '@/components/cron/CronPanel'
import { SkillsPanel } from '@/components/skills/SkillsPanel'
import { LogsPanel } from '@/components/logs/LogsPanel'
import { ConfigPanel } from '@/components/config/ConfigPanel'
import { DebugPanel } from '@/components/debug/DebugPanel'
import { NodesPanel } from '@/components/nodes/NodesPanel'
import { LoginPage } from '@/components/auth/LoginPage'
import { SetupPage } from '@/components/auth/SetupPage'
import { useUIStore } from '@/stores/uiStore'
import { WebSocketProvider } from '@/hooks/useWebSocket'
import { ToastProvider } from '@/components/ui/Toast'
import { SystemProvider } from '@/contexts/SystemContext'
import { Loader2 } from 'lucide-react'

function App() {
  const [activeView, setActiveView] = useState<ViewType>('chat')
  const { 
    authStatus, 
    setAuthStatus, 
    isAuthenticated, 
    setAuthenticated,
    authLoading,
    setAuthLoading 
  } = useUIStore()

  // Check auth status on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch('/api/auth/status')
        const data = await response.json()
        
        setAuthStatus(data)
        setAuthenticated(data.authenticated || false)
      } catch (error) {
        console.error('Auth check failed:', error)
        // If auth check fails, assume no auth configured
        setAuthStatus({ configured: false, authenticated: false, pin_configured: false, require_pin: false, session_duration_days: 7 })
        setAuthenticated(false)
      } finally {
        setAuthLoading(false)
      }
    }
    
    checkAuth()
  }, [setAuthStatus, setAuthenticated, setAuthLoading])

  const handleLoginSuccess = () => {
    setAuthenticated(true)
    // Refresh auth status
    fetch('/api/auth/status')
      .then(res => res.json())
      .then(data => setAuthStatus(data))
      .catch(console.error)
  }

  const handleSetupComplete = () => {
    setAuthenticated(true)
    // Refresh auth status
    fetch('/api/auth/status')
      .then(res => res.json())
      .then(data => setAuthStatus(data))
      .catch(console.error)
  }

  const renderMainContent = () => {
    switch (activeView) {
      case 'chat':
        return <ChatPanel />
      case 'overview':
        return <OverviewPanel />
      case 'channels':
        return <ChannelsPanel />
      case 'sessions':
        return <SessionsPanel />
      case 'settings':
        return <SettingsPanel />
      case 'activity':
        return <ActivityPanel />
      case 'subagents':
        return <SubAgentsPanel />
      case 'team':
        return <TeamPanel />
      case 'cron':
        return <CronPanel />
      case 'skills':
        return <SkillsPanel />
      case 'nodes':
        return <NodesPanel />
      case 'logs':
        return <LogsPanel />
      case 'config':
        return <ConfigPanel />
      case 'debug':
        return <DebugPanel />
      default:
        return <ChatPanel />
    }
  }

  // Loading state
  if (authLoading) {
    return (
      <div className="min-h-screen bg-giga-dark flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={48} className="animate-spin text-giga-accent mx-auto mb-4" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  // First-run: Show setup page if setup hasn't been completed
  // This ensures users configure auth before using the dashboard
  if (authStatus?.setup_complete === false) {
    return <SetupPage onSetupComplete={handleSetupComplete} />
  }

  // Auth configured but not authenticated - show login
  if (authStatus?.configured && !isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />
  }

  // Note: If auth is not configured (setup_complete=true but no password),
  // allow direct access (backwards compatible)

  return (
    <ToastProvider>
      <SystemProvider>
        <WebSocketProvider>
          <div className="flex h-screen bg-giga-dark overflow-hidden">
            {/* Sidebar - Hidden on mobile */}
            <Sidebar
              activeView={activeView}
              onViewChange={setActiveView}
              className="hidden md:flex"
            />

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Header */}
              <Header />

              {/* Main Content */}
              <main className="flex-1 overflow-hidden">
                {renderMainContent()}
              </main>
            </div>

            {/* Bottom Navigation - Mobile only */}
            <BottomNav
              activeView={activeView}
              onViewChange={setActiveView}
              className="md:hidden"
            />
          </div>
        </WebSocketProvider>
      </SystemProvider>
    </ToastProvider>
  )
}

export default App
