import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'

/**
 * System state from backend.
 * 
 * Provides single source of truth for:
 * - Agent lifecycle state
 * - Provider configuration status
 * - System health
 */
export interface SystemState {
  agentState: 'uninitialized' | 'initializing' | 'ready' | 'error'
  isReady: boolean
  hasApiKey: boolean
  configuredProviders: string[]
  primaryProvider: string | null
  version: string
  error: string | null
  model: string | null
  workspace: string | null
  tieredRoutingEnabled: boolean
  memoryEnabled: boolean
  swarmEnabled: boolean
  tracking: {
    total_tokens?: number
    estimated_cost?: number
    session?: {
      total_tokens?: number
      estimated_cost?: number
    }
  } | null
}

interface SystemContextValue extends SystemState {
  refresh: () => Promise<void>
  reinitialize: () => Promise<boolean>
  loading: boolean
}

const defaultState: SystemState = {
  agentState: 'uninitialized',
  isReady: false,
  hasApiKey: false,
  configuredProviders: [],
  primaryProvider: null,
  version: '0.1.0',
  error: null,
  model: null,
  workspace: null,
  tieredRoutingEnabled: false,
  memoryEnabled: false,
  swarmEnabled: false,
  tracking: null,
}

const SystemContext = createContext<SystemContextValue | null>(null)

interface SystemProviderProps {
  children: ReactNode
  pollInterval?: number // in milliseconds
}

export function SystemProvider({ children, pollInterval = 5000 }: SystemProviderProps) {
  const [state, setState] = useState<SystemState>(defaultState)
  const [loading, setLoading] = useState(true)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/system/status')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = await res.json()
      
      setState({
        agentState: data.agent_state || 'uninitialized',
        isReady: data.is_ready || false,
        hasApiKey: data.has_api_key || false,
        configuredProviders: data.configured_providers || [],
        primaryProvider: data.primary_provider || null,
        version: data.version || '0.1.0',
        error: data.error || null,
        model: data.model || null,
        workspace: data.workspace || null,
        tieredRoutingEnabled: data.tiered_routing_enabled || false,
        memoryEnabled: data.memory_enabled || false,
        swarmEnabled: data.swarm_enabled || false,
        tracking: data.tracking || null,
      })
    } catch (error) {
      console.error('Failed to fetch system status:', error)
      // Don't update state on error - keep last known state
    } finally {
      setLoading(false)
    }
  }, [])

  const reinitialize = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch('/api/system/reinitialize', { method: 'POST' })
      const data = await res.json()
      
      // Refresh status after reinitialize
      await fetchStatus()
      
      return data.success || false
    } catch (error) {
      console.error('Failed to reinitialize agent:', error)
      return false
    }
  }, [fetchStatus])

  // Initial fetch
  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Poll for status updates
  useEffect(() => {
    if (pollInterval <= 0) return

    const interval = setInterval(fetchStatus, pollInterval)
    return () => clearInterval(interval)
  }, [fetchStatus, pollInterval])

  const value: SystemContextValue = {
    ...state,
    refresh: fetchStatus,
    reinitialize,
    loading,
  }

  return (
    <SystemContext.Provider value={value}>
      {children}
    </SystemContext.Provider>
  )
}

/**
 * Hook to access system state.
 * 
 * Usage:
 * ```tsx
 * const { agentState, hasApiKey, isReady } = useSystem()
 * 
 * if (!hasApiKey) {
 *   return <ConfigureApiKeyPrompt />
 * }
 * ```
 */
export function useSystem(): SystemContextValue {
  const context = useContext(SystemContext)
  if (!context) {
    throw new Error('useSystem must be used within a SystemProvider')
  }
  return context
}

/**
 * Hook to check if chat is available.
 * 
 * Returns:
 * - available: boolean - Whether chat can be used
 * - reason: string | null - Why chat is not available (if applicable)
 */
export function useChatAvailability(): { available: boolean; reason: string | null } {
  const { isReady, agentState, error, hasApiKey } = useSystem()
  
  if (isReady) {
    return { available: true, reason: null }
  }
  
  if (!hasApiKey) {
    return { 
      available: false, 
      reason: 'No API key configured. Go to Settings > Providers to add one.' 
    }
  }
  
  if (agentState === 'initializing') {
    return { 
      available: false, 
      reason: 'Agent is initializing, please wait...' 
    }
  }
  
  if (agentState === 'error') {
    return { 
      available: false, 
      reason: error || 'Agent initialization failed. Check Settings > Providers.' 
    }
  }
  
  return { 
    available: false, 
    reason: 'Agent is not ready.' 
  }
}
