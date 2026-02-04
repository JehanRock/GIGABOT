import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Key, 
  Palette, 
  Bell, 
  Shield, 
  Database,
  Save,
  RefreshCw,
  Moon,
  Sun,
  Info,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Star,
  Zap,
  TestTube,
  Loader2,
  Server,
  Layers,
  Users,
  Brain,
  Settings2,
  Check
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useConfig } from '@/hooks/useStatus'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { UserModeToggle } from './UserModeToggle'
import { useToast } from '@/components/ui/Toast'
import type { Gateway, GatewayProvider, RoutingConfig, MemoryConfig, TeamConfigResponse } from '@/types'

type SettingsTab = 'general' | 'security' | 'notifications' | 'advanced' | 'providers' | 'routing' | 'team' | 'memory'

const PROVIDER_INFO: Record<GatewayProvider, { name: string; icon: string; color: string }> = {
  openrouter: { name: 'OpenRouter', icon: '🌐', color: 'text-blue-400' },
  anthropic: { name: 'Anthropic', icon: '🧠', color: 'text-orange-400' },
  openai: { name: 'OpenAI', icon: '⚡', color: 'text-green-400' },
  moonshot: { name: 'Moonshot', icon: '🌙', color: 'text-purple-400' },
  deepseek: { name: 'DeepSeek', icon: '🔍', color: 'text-cyan-400' },
  glm: { name: 'GLM (Zhipu)', icon: '🇨🇳', color: 'text-red-400' },
  qwen: { name: 'Qwen', icon: '🔮', color: 'text-yellow-400' },
  ollama: { name: 'Ollama', icon: '🦙', color: 'text-gray-400' },
  vllm: { name: 'vLLM', icon: '🚀', color: 'text-pink-400' },
}

export function SettingsPanel() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const { theme, toggleTheme, authToken, setAuthToken } = useUIStore()
  const { data: config, isLoading } = useConfig()
  
  const [tokenInput, setTokenInput] = useState(authToken || '')
  const [isSaving, setIsSaving] = useState(false)
  
  // Gateway state
  const [showAddGateway, setShowAddGateway] = useState(false)
  const [newGateway, setNewGateway] = useState({
    name: '',
    provider: 'openrouter' as GatewayProvider,
    api_key: '',
    api_base: '',
    is_primary: false,
    is_fallback: true,
  })
  const [testingGatewayId, setTestingGatewayId] = useState<string | null>(null)

  // Provider API keys state
  const [providerKeys, setProviderKeys] = useState<Record<GatewayProvider, string>>({
    openrouter: '',
    anthropic: '',
    openai: '',
    moonshot: '',
    deepseek: '',
    glm: '',
    qwen: '',
    ollama: '',
    vllm: '',
  })
  const [savingProvider, setSavingProvider] = useState<string | null>(null)

  // Routing state
  const [routingEnabled, setRoutingEnabled] = useState(true)
  const [fallbackEnabled, setFallbackEnabled] = useState(true)
  const [tierModels, setTierModels] = useState<Record<string, string>>({
    tier1: 'anthropic/claude-opus-4.5',
    tier2: 'anthropic/claude-sonnet-4.5',
    tier3: 'google/gemini-3-flash',
  })

  // Memory state
  const [memoryEnabled, setMemoryEnabled] = useState(true)
  const [vectorSearch, setVectorSearch] = useState(true)
  const [contextMemories, setContextMemories] = useState(5)

  // Team state
  const [teamEnabled, setTeamEnabled] = useState(false)
  const [qaGateEnabled, setQaGateEnabled] = useState(true)
  const [auditGateEnabled, setAuditGateEnabled] = useState(true)
  const [swarmEnabled, setSwarmEnabled] = useState(false)
  const [maxWorkers, setMaxWorkers] = useState(3)

  // Fetch providers
  const { data: providersData } = useQuery({
    queryKey: ['providers'],
    queryFn: () => api.getProviders(),
    staleTime: 30000,
  })

  // Fetch routing config
  const { data: routingData } = useQuery({
    queryKey: ['routing'],
    queryFn: () => api.getRouting(),
    staleTime: 30000,
  })

  // Fetch memory config
  const { data: memoryData } = useQuery({
    queryKey: ['memoryConfig'],
    queryFn: () => api.getMemoryConfig(),
    staleTime: 30000,
  })

  // Fetch team config
  const { data: teamData } = useQuery({
    queryKey: ['teamConfig'],
    queryFn: () => api.getTeamConfig(),
    staleTime: 30000,
  })

  // Sync state with fetched data
  useEffect(() => {
    if (routingData) {
      setRoutingEnabled(routingData.enabled)
      if (routingData.tiers) {
        const models: Record<string, string> = {}
        Object.entries(routingData.tiers).forEach(([tier, config]) => {
          if (config.models && config.models.length > 0) {
            models[tier] = config.models[0]
          }
        })
        if (Object.keys(models).length > 0) {
          setTierModels(prev => ({ ...prev, ...models }))
        }
      }
    }
  }, [routingData])

  useEffect(() => {
    if (memoryData) {
      setMemoryEnabled(memoryData.enabled)
      setVectorSearch(memoryData.vector_search)
      setContextMemories(memoryData.context_memories)
    }
  }, [memoryData])

  useEffect(() => {
    if (teamData) {
      setTeamEnabled(teamData.team.enabled)
      setQaGateEnabled(teamData.team.qa_gate_enabled)
      setAuditGateEnabled(teamData.team.audit_gate_enabled)
      setSwarmEnabled(teamData.swarm.enabled)
      setMaxWorkers(teamData.swarm.max_workers)
    }
  }, [teamData])

  // Provider mutation
  const updateProviderMutation = useMutation({
    mutationFn: ({ provider, apiKey }: { provider: string; apiKey: string }) =>
      api.updateProvider(provider, { api_key: apiKey }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['providers'] })
      setSavingProvider(null)
      // Clear the input after successful save
      setProviderKeys(prev => ({ ...prev, [variables.provider]: '' }))
      toast.success(`${variables.provider} API key saved successfully`)
    },
    onError: (error, variables) => {
      setSavingProvider(null)
      toast.error(`Failed to save ${variables.provider} API key: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Routing mutation
  const updateRoutingMutation = useMutation({
    mutationFn: (data: Partial<RoutingConfig>) => api.updateRouting(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing'] })
      toast.success('Routing configuration saved')
    },
    onError: (error) => {
      toast.error(`Failed to save routing: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Memory mutation
  const updateMemoryMutation = useMutation({
    mutationFn: (data: Partial<MemoryConfig>) => api.updateMemoryConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memoryConfig'] })
      toast.success('Memory configuration saved')
    },
    onError: (error) => {
      toast.error(`Failed to save memory settings: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Team mutation
  const updateTeamMutation = useMutation({
    mutationFn: (data: { team?: Partial<TeamConfigResponse['team']>; swarm?: Partial<TeamConfigResponse['swarm']> }) =>
      api.updateTeamConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamConfig'] })
      toast.success('Team configuration saved')
    },
    onError: (error) => {
      toast.error(`Failed to save team settings: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Handler functions
  const handleSaveProviderKey = (provider: GatewayProvider) => {
    const apiKey = providerKeys[provider]
    if (apiKey.trim()) {
      setSavingProvider(provider)
      updateProviderMutation.mutate({ provider, apiKey })
    }
  }

  const handleSaveRouting = () => {
    updateRoutingMutation.mutate({
      enabled: routingEnabled,
      tiers: {
        tier1: { models: [tierModels.tier1], triggers: ['complex', 'reasoning'] },
        tier2: { models: [tierModels.tier2], triggers: ['general'] },
        tier3: { models: [tierModels.tier3], triggers: ['simple', 'fast'] },
      },
    })
  }

  const handleSaveMemory = () => {
    updateMemoryMutation.mutate({
      enabled: memoryEnabled,
      vector_search: vectorSearch,
      context_memories: contextMemories,
    })
  }

  const handleSaveTeam = () => {
    updateTeamMutation.mutate({
      team: {
        enabled: teamEnabled,
        qa_gate_enabled: qaGateEnabled,
        audit_gate_enabled: auditGateEnabled,
      },
      swarm: {
        enabled: swarmEnabled,
        max_workers: maxWorkers,
      },
    })
  }

  // Fetch gateways
  const { data: gatewaysData, isLoading: gatewaysLoading } = useQuery({
    queryKey: ['gateways'],
    queryFn: () => api.getGateways(),
    staleTime: 30000,
  })

  // Add gateway mutation
  const addGatewayMutation = useMutation({
    mutationFn: (gateway: typeof newGateway) => api.addGateway(gateway),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
      setShowAddGateway(false)
      setNewGateway({
        name: '',
        provider: 'openrouter',
        api_key: '',
        api_base: '',
        is_primary: false,
        is_fallback: true,
      })
      toast.success('Gateway added successfully')
    },
    onError: (error) => {
      toast.error(`Failed to add gateway: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Update gateway mutation
  const updateGatewayMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<Gateway> }) =>
      api.updateGateway(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
      toast.success('Gateway updated')
    },
    onError: (error) => {
      toast.error(`Failed to update gateway: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Delete gateway mutation
  const deleteGatewayMutation = useMutation({
    mutationFn: (id: string) => api.deleteGateway(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
      toast.success('Gateway deleted')
    },
    onError: (error) => {
      toast.error(`Failed to delete gateway: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  // Test gateway mutation
  const testGatewayMutation = useMutation({
    mutationFn: (id: string) => {
      setTestingGatewayId(id)
      return api.testGateway(id)
    },
    onSuccess: (result) => {
      if (result.success) {
        toast.success('Gateway connection successful')
      } else {
        toast.warning(`Gateway test: ${result.error || 'Connection issue'}`)
      }
    },
    onError: (error) => {
      toast.error(`Gateway test failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
    onSettled: () => {
      setTestingGatewayId(null)
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
    },
  })

  const handleSaveToken = () => {
    setAuthToken(tokenInput || null)
    setIsSaving(true)
    setTimeout(() => setIsSaving(false), 500)
  }

  const handleSetPrimary = (gatewayId: string) => {
    updateGatewayMutation.mutate({ id: gatewayId, updates: { is_primary: true } })
  }

  const handleToggleFallback = (gateway: Gateway) => {
    updateGatewayMutation.mutate({
      id: gateway.id,
      updates: { is_fallback: !gateway.is_fallback },
    })
  }

  const handleToggleEnabled = (gateway: Gateway) => {
    updateGatewayMutation.mutate({
      id: gateway.id,
      updates: { enabled: !gateway.enabled },
    })
  }

  const { userMode } = useUIStore()
  const isAdvanced = userMode === 'advanced'

  const standardTabs = [
    { id: 'general' as const, label: 'General', icon: <Palette size={18} /> },
    { id: 'providers' as const, label: 'Providers', icon: <Server size={18} /> },
    { id: 'security' as const, label: 'Security', icon: <Shield size={18} /> },
    { id: 'notifications' as const, label: 'Notifications', icon: <Bell size={18} /> },
  ]

  const advancedTabs = [
    { id: 'general' as const, label: 'General', icon: <Palette size={18} /> },
    { id: 'security' as const, label: 'Security', icon: <Shield size={18} /> },
    { id: 'providers' as const, label: 'Providers', icon: <Server size={18} /> },
    { id: 'routing' as const, label: 'Routing', icon: <Layers size={18} /> },
    { id: 'memory' as const, label: 'Memory', icon: <Brain size={18} /> },
    { id: 'team' as const, label: 'Team', icon: <Users size={18} /> },
    { id: 'notifications' as const, label: 'Notifications', icon: <Bell size={18} /> },
    { id: 'advanced' as const, label: 'Advanced', icon: <Database size={18} /> },
  ]

  const tabs = isAdvanced ? advancedTabs : standardTabs

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure your GigaBot dashboard preferences
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg whitespace-nowrap transition-colors',
                activeTab === tab.id
                  ? 'bg-giga-accent text-white'
                  : 'bg-giga-card text-gray-400 hover:text-white'
              )}
            >
              {tab.icon}
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="space-y-6">
          {activeTab === 'general' && (
            <>
              {/* User Mode */}
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Dashboard Mode</h3>
                <UserModeToggle />
              </div>

              {/* Theme */}
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Appearance</h3>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-300">Theme</p>
                    <p className="text-xs text-gray-500">Choose your preferred color scheme</p>
                  </div>
                  <button
                    onClick={toggleTheme}
                    className="flex items-center gap-2 px-4 py-2 bg-giga-hover rounded-lg transition-colors"
                  >
                    {theme === 'dark' ? (
                      <>
                        <Moon size={18} className="text-giga-accent" />
                        <span className="text-sm text-gray-300">Dark</span>
                      </>
                    ) : (
                      <>
                        <Sun size={18} className="text-giga-warning" />
                        <span className="text-sm text-gray-300">Light</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Model Info - Only in advanced mode */}
              {isAdvanced && config && (
                <div className="card">
                  <h3 className="font-semibold text-white mb-4">Current Configuration</h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-b border-sidebar-border">
                      <span className="text-sm text-gray-400">Model</span>
                      <span className="text-sm text-white font-mono">
                        {config.agents?.model || 'Not configured'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-sidebar-border">
                      <span className="text-sm text-gray-400">Max Tokens</span>
                      <span className="text-sm text-white font-mono">
                        {config.agents?.max_tokens || 'Default'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-400">Tiered Routing</span>
                      <span className={cn(
                        'text-sm font-medium',
                        config.agents?.tiered_routing ? 'text-giga-success' : 'text-gray-500'
                      )}>
                        {config.agents?.tiered_routing ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'security' && (
            <>
              {/* Auth Token */}
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Dashboard Access</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      <Key size={14} className="inline mr-2" />
                      Dashboard Token
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={tokenInput}
                        onChange={(e) => setTokenInput(e.target.value)}
                        placeholder="Enter your gateway token..."
                        className="input flex-1"
                      />
                      <button
                        onClick={handleSaveToken}
                        disabled={isSaving}
                        className="btn-primary flex items-center gap-2"
                      >
                        <Save size={16} />
                        {isSaving ? 'Saved!' : 'Save'}
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      This token is used to secure access to the GigaBot dashboard and API. 
                      It is NOT for LLM providers (use the Providers tab for that).
                    </p>
                  </div>
                </div>
              </div>

              {/* Security Mode */}
              {config?.security && (
                <div className="card">
                  <h3 className="font-semibold text-white mb-4">Security Mode</h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-b border-sidebar-border">
                      <span className="text-sm text-gray-400">Auth Mode</span>
                      <span className="badge-primary">{config.security.auth_mode}</span>
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-400">Sandbox Mode</span>
                      <span className="badge-warning">{config.security.sandbox_mode}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'notifications' && (
            <div className="card">
              <h3 className="font-semibold text-white mb-4">Notification Preferences</h3>
              <div className="space-y-4">
                {[
                  { label: 'New messages', description: 'Get notified when new messages arrive' },
                  { label: 'Channel status', description: 'Alert when channels go offline' },
                  { label: 'Error alerts', description: 'Important error notifications' },
                  { label: 'Usage warnings', description: 'Token and cost limit warnings' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-sm font-medium text-gray-300">{item.label}</p>
                      <p className="text-xs text-gray-500">{item.description}</p>
                    </div>
                    <button className="w-12 h-6 rounded-full bg-giga-success relative">
                      <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Providers Tab - Available in both modes */}
          {activeTab === 'providers' && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">LLM Providers & Gateways</h3>
                <p className="text-xs text-gray-500 mb-4">
                  Configure API keys for LLM providers. OpenRouter is the default gateway.
                </p>
                <div className="space-y-4">
                  {Object.entries(PROVIDER_INFO).map(([key, info]) => {
                    const provider = key as GatewayProvider
                    const hasKey = providersData?.providers?.[provider]?.has_key || false
                    const isSaving = savingProvider === provider
                    const isDefault = provider === 'openrouter'
                    
                    return (
                      <div key={key} className={cn(
                        "p-4 rounded-lg border transition-colors",
                        hasKey ? "bg-giga-hover border-giga-success/30" : "bg-giga-card border-sidebar-border"
                      )}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <span className="text-xl">{info.icon}</span>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className={cn('font-medium', info.color)}>{info.name}</span>
                                {isDefault && (
                                  <span className="px-2 py-0.5 text-[10px] bg-giga-accent/20 text-giga-accent rounded-full border border-giga-accent/30">
                                    Default Gateway
                                  </span>
                                )}
                              </div>
                              {hasKey && (
                                <div className="flex items-center gap-1 text-xs text-giga-success mt-1">
                                  <CheckCircle size={12} />
                                  <span>Active & Ready</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <input
                            type="password"
                            placeholder={hasKey ? '••••••••••••••••' : `Enter ${info.name} API Key`}
                            value={providerKeys[provider]}
                            onChange={(e) => setProviderKeys(prev => ({ ...prev, [provider]: e.target.value }))}
                            className="input flex-1 font-mono text-sm"
                          />
                          <button 
                            className="btn-secondary flex items-center gap-2"
                            onClick={() => handleSaveProviderKey(provider)}
                            disabled={isSaving || !providerKeys[provider].trim()}
                          >
                            {isSaving ? (
                              <Loader2 size={16} className="animate-spin" />
                            ) : (
                              <Save size={16} />
                            )}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}

          {/* Routing Tab - Advanced only */}
          {activeTab === 'routing' && isAdvanced && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Model Tier Configuration</h3>
                <p className="text-xs text-gray-500 mb-4">Configure which models are used for each tier</p>
                
                <div className="space-y-4">
                  {[
                    { key: 'tier1', tier: 'Tier 1', description: 'Most capable, used for complex reasoning', color: 'purple' },
                    { key: 'tier2', tier: 'Tier 2', description: 'Balanced performance and cost', color: 'blue' },
                    { key: 'tier3', tier: 'Tier 3', description: 'Fast responses, lower cost', color: 'green' },
                  ].map((t) => (
                    <div key={t.tier} className={cn('p-4 rounded-lg border', `border-${t.color}-500/30 bg-${t.color}-500/10`)}>
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className={`font-medium text-${t.color}-400`}>{t.tier}</h4>
                          <p className="text-xs text-gray-500">{t.description}</p>
                        </div>
                      </div>
                      <select 
                        className="input w-full"
                        value={tierModels[t.key] || ''}
                        onChange={(e) => setTierModels(prev => ({ ...prev, [t.key]: e.target.value }))}
                      >
                        <option value="moonshot/kimi-k2.5">KIMI K2.5 (Moonshot AI)</option>
                        <option value="anthropic/claude-opus-4.5">Claude Opus 4.5 (Anthropic)</option>
                        <option value="anthropic/claude-sonnet-4.5">Claude Sonnet 4.5 (Anthropic)</option>
                        <option value="google/gemini-3-pro">Gemini 3 Pro (Google)</option>
                        <option value="google/gemini-3-flash">Gemini 3 Flash (Google)</option>
                        <option value="openai/gpt-5.2">GPT 5.2 (OpenAI)</option>
                        <option value="stepfun/step-3.5-flash">Step 3.5 Flash (StepFun)</option>
                        <option value="deepseek/deepseek-v3.2">Deepseek V3.2 (Deepseek)</option>
                        <option value="glm/glm-4.7">GLM 4.7 (Zhipu AI)</option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-white mb-4">Routing Rules</h3>
                <div className="space-y-3">
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Enable Tiered Routing</p>
                      <p className="text-xs text-gray-500">Automatically select model based on task complexity</p>
                    </div>
                    <button
                      onClick={() => setRoutingEnabled(!routingEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        routingEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        routingEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Fallback on Error</p>
                      <p className="text-xs text-gray-500">Try next tier if current tier fails</p>
                    </div>
                    <button
                      onClick={() => setFallbackEnabled(!fallbackEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        fallbackEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        fallbackEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                </div>
              </div>

              <button 
                className="btn-primary w-full flex items-center justify-center gap-2"
                onClick={handleSaveRouting}
                disabled={updateRoutingMutation.isPending}
              >
                {updateRoutingMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                Save Routing Configuration
              </button>
            </>
          )}

          {/* Memory Tab - Advanced only */}
          {activeTab === 'memory' && isAdvanced && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Memory Configuration</h3>
                <div className="space-y-4">
                  <label className="flex items-center justify-between py-2 border-b border-sidebar-border cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Enable Memory System</p>
                      <p className="text-xs text-gray-500">Store and retrieve conversation context</p>
                    </div>
                    <button
                      onClick={() => setMemoryEnabled(!memoryEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        memoryEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        memoryEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  <label className="flex items-center justify-between py-2 border-b border-sidebar-border cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Vector Search</p>
                      <p className="text-xs text-gray-500">Enable semantic search for memories</p>
                    </div>
                    <button
                      onClick={() => setVectorSearch(!vectorSearch)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        vectorSearch ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        vectorSearch ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-sm text-gray-300">Context Memories</p>
                      <p className="text-xs text-gray-500">Number of memories to include in context</p>
                    </div>
                    <input 
                      type="number" 
                      value={contextMemories} 
                      onChange={(e) => setContextMemories(parseInt(e.target.value) || 5)}
                      min={1}
                      max={20}
                      className="input w-24 text-center" 
                    />
                  </div>
                </div>
              </div>

              <button 
                className="btn-primary w-full flex items-center justify-center gap-2"
                onClick={handleSaveMemory}
                disabled={updateMemoryMutation.isPending}
              >
                {updateMemoryMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                Save Memory Configuration
              </button>

              <div className="card">
                <h3 className="font-semibold text-white mb-4">Memory Actions</h3>
                <div className="space-y-3">
                  <button className="w-full flex items-center justify-between p-3 bg-giga-hover rounded-lg hover:bg-giga-card transition-colors">
                    <div className="flex items-center gap-3">
                      <Brain size={18} className="text-giga-accent" />
                      <span className="text-sm text-gray-300">Reindex All Memories</span>
                    </div>
                  </button>
                  <button className="w-full flex items-center justify-between p-3 bg-giga-warning/10 border border-giga-warning/20 rounded-lg hover:bg-giga-warning/20 transition-colors">
                    <div className="flex items-center gap-3">
                      <Trash2 size={18} className="text-giga-warning" />
                      <span className="text-sm text-giga-warning">Clear Memory Index</span>
                    </div>
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Team Tab - Advanced only */}
          {activeTab === 'team' && isAdvanced && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Team Configuration</h3>
                <div className="space-y-4">
                  <label className="flex items-center justify-between py-2 border-b border-sidebar-border cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Enable Team Mode</p>
                      <p className="text-xs text-gray-500">Use multiple agents for complex tasks</p>
                    </div>
                    <button
                      onClick={() => setTeamEnabled(!teamEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        teamEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        teamEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  <label className="flex items-center justify-between py-2 border-b border-sidebar-border cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Enable Swarm</p>
                      <p className="text-xs text-gray-500">Parallel worker agents for intensive tasks</p>
                    </div>
                    <button
                      onClick={() => setSwarmEnabled(!swarmEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        swarmEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        swarmEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  {swarmEnabled && (
                    <div className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-sm text-gray-300">Max Workers</p>
                        <p className="text-xs text-gray-500">Maximum concurrent worker agents</p>
                      </div>
                      <input 
                        type="number" 
                        value={maxWorkers} 
                        onChange={(e) => setMaxWorkers(parseInt(e.target.value) || 3)}
                        min={1}
                        max={10}
                        className="input w-24 text-center" 
                      />
                    </div>
                  )}
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-white mb-4">Quality Gate Settings</h3>
                <div className="space-y-3">
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Require Code Review</p>
                      <p className="text-xs text-gray-500">All code must pass reviewer before merging</p>
                    </div>
                    <button
                      onClick={() => setQaGateEnabled(!qaGateEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        qaGateEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        qaGateEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Security Audit</p>
                      <p className="text-xs text-gray-500">Run security checks on all outputs</p>
                    </div>
                    <button
                      onClick={() => setAuditGateEnabled(!auditGateEnabled)}
                      className={cn(
                        'w-12 h-6 rounded-full relative transition-colors',
                        auditGateEnabled ? 'bg-giga-success' : 'bg-gray-600'
                      )}
                    >
                      <span className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-all',
                        auditGateEnabled ? 'right-1' : 'left-1'
                      )} />
                    </button>
                  </label>
                </div>
              </div>

              <button 
                className="btn-primary w-full flex items-center justify-center gap-2"
                onClick={handleSaveTeam}
                disabled={updateTeamMutation.isPending}
              >
                {updateTeamMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                Save Team Configuration
              </button>
            </>
          )}

          {activeTab === 'advanced' && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Dashboard Version</h3>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white font-mono">v0.1.0</p>
                    <p className="text-xs text-gray-500">Current dashboard version</p>
                  </div>
                  <button className="btn-secondary flex items-center gap-2">
                    <RefreshCw size={16} />
                    Check for Updates
                  </button>
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-white mb-4">Data Management</h3>
                <div className="space-y-3">
                  <button className="w-full flex items-center justify-between p-3 bg-giga-hover rounded-lg hover:bg-giga-card transition-colors">
                    <div className="flex items-center gap-3">
                      <Database size={18} className="text-gray-400" />
                      <span className="text-sm text-gray-300">Export All Data</span>
                    </div>
                  </button>
                  <button className="w-full flex items-center justify-between p-3 bg-giga-error/10 border border-giga-error/20 rounded-lg hover:bg-giga-error/20 transition-colors">
                    <div className="flex items-center gap-3">
                      <Database size={18} className="text-giga-error" />
                      <span className="text-sm text-giga-error">Clear Local Data</span>
                    </div>
                  </button>
                </div>
              </div>

              {/* Info */}
              <div className="p-4 bg-giga-accent/10 border border-giga-accent/20 rounded-xl">
                <div className="flex items-start gap-3">
                  <Info size={20} className="text-giga-accent flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-white">About GigaBot Dashboard</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Built with React, TanStack Query, and TailwindCSS. 
                      This dashboard provides a modern interface for managing your GigaBot instance.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
