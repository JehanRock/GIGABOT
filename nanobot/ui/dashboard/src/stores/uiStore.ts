import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthStatus {
  configured: boolean
  pin_configured: boolean
  require_pin: boolean
  authenticated: boolean
  session_duration_days: number
  setup_complete?: boolean  // True once initial setup wizard has been run
}

export type UserMode = 'standard' | 'advanced'

interface UIState {
  // User Mode
  userMode: UserMode
  setUserMode: (mode: UserMode) => void

  // Sidebar
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void

  // Theme
  theme: 'dark' | 'light'
  toggleTheme: () => void

  // Connection
  connectionStatus: 'connected' | 'connecting' | 'disconnected'
  setConnectionStatus: (status: 'connected' | 'connecting' | 'disconnected') => void

  // Chat
  activeChatId: string | null
  setActiveChatId: (id: string | null) => void

  // Mobile menu
  mobileMenuOpen: boolean
  setMobileMenuOpen: (open: boolean) => void

  // Settings panel
  settingsPanelOpen: boolean
  setSettingsPanelOpen: (open: boolean) => void

  // Auth token (for API)
  authToken: string | null
  setAuthToken: (token: string | null) => void
  
  // Dashboard authentication state
  authStatus: AuthStatus | null
  setAuthStatus: (status: AuthStatus | null) => void
  isAuthenticated: boolean
  setAuthenticated: (auth: boolean) => void
  authLoading: boolean
  setAuthLoading: (loading: boolean) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // User Mode
      userMode: 'standard',
      setUserMode: (mode) => set({ userMode: mode }),

      // Sidebar
      sidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      // Theme
      theme: 'dark',
      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'dark' ? 'light' : 'dark',
        })),

      // Connection
      connectionStatus: 'disconnected',
      setConnectionStatus: (status) => set({ connectionStatus: status }),

      // Chat
      activeChatId: null,
      setActiveChatId: (id) => set({ activeChatId: id }),

      // Mobile menu
      mobileMenuOpen: false,
      setMobileMenuOpen: (open) => set({ mobileMenuOpen: open }),

      // Settings panel
      settingsPanelOpen: false,
      setSettingsPanelOpen: (open) => set({ settingsPanelOpen: open }),

      // Auth token
      authToken: null,
      setAuthToken: (token) => set({ authToken: token }),
      
      // Dashboard authentication state
      authStatus: null,
      setAuthStatus: (status) => set({ authStatus: status }),
      isAuthenticated: false,
      setAuthenticated: (auth) => set({ isAuthenticated: auth }),
      authLoading: true,
      setAuthLoading: (loading) => set({ authLoading: loading }),
    }),
    {
      name: 'gigabot-ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
        authToken: state.authToken,
        userMode: state.userMode,
      }),
    }
  )
)
