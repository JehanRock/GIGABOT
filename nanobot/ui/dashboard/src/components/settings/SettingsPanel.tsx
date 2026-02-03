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
  Settings2
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useConfig } from '@/hooks/useStatus'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { UserModeToggle } from './UserModeToggle'
import type { Gateway, GatewayProvider } from '@/types'

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
    },
  })

  // Update gateway mutation
  const updateGatewayMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<Gateway> }) =>
      api.updateGateway(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
    },
  })

  // Delete gateway mutation
  const deleteGatewayMutation = useMutation({
    mutationFn: (id: string) => api.deleteGateway(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gateways'] })
    },
  })

  // Test gateway mutation
  const testGatewayMutation = useMutation({
    mutationFn: (id: string) => {
      setTestingGatewayId(id)
      return api.testGateway(id)
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
              {/* LLM Gateways */}
              <div className="card">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white flex items-center gap-2">
                      <Server size={18} />
                      LLM Gateways
                    </h3>
                    <p className="text-xs text-gray-500 mt-1">
                      Configure API gateways with automatic fallback
                    </p>
                  </div>
                  <button
                    onClick={() => setShowAddGateway(true)}
                    className="btn-primary flex items-center gap-2 text-sm"
                  >
                    <Plus size={16} />
                    Add Gateway
                  </button>
                </div>

                {/* Gateway List */}
                <div className="space-y-3">
                  {gatewaysLoading ? (
                    <div className="flex items-center justify-center py-8 text-gray-400">
                      <Loader2 size={20} className="animate-spin mr-2" />
                      Loading gateways...
                    </div>
                  ) : gatewaysData?.gateways.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      <Server size={32} className="mx-auto mb-2 opacity-50" />
                      <p>No gateways configured</p>
                      <p className="text-xs mt-1">Add a gateway to connect to an LLM provider</p>
                    </div>
                  ) : (
                    gatewaysData?.gateways.map((gateway) => (
                      <div
                        key={gateway.id}
                        className={cn(
                          'p-4 rounded-lg border transition-colors',
                          gateway.enabled
                            ? 'bg-giga-hover border-sidebar-border'
                            : 'bg-giga-card/50 border-sidebar-border/50 opacity-60'
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">
                              {PROVIDER_INFO[gateway.provider]?.icon || '🔌'}
                            </span>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white">{gateway.name}</span>
                                {gateway.is_primary && (
                                  <span className="px-2 py-0.5 text-xs bg-giga-accent text-white rounded-full flex items-center gap-1">
                                    <Star size={10} fill="currentColor" />
                                    Primary
                                  </span>
                                )}
                                {gateway.is_fallback && !gateway.is_primary && (
                                  <span className="px-2 py-0.5 text-xs bg-giga-warning/20 text-giga-warning rounded-full flex items-center gap-1">
                                    <Zap size={10} />
                                    Fallback
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className={cn('text-xs', PROVIDER_INFO[gateway.provider]?.color)}>
                                  {PROVIDER_INFO[gateway.provider]?.name}
                                </span>
                                <span className="text-gray-600">•</span>
                                {gateway.health_status === 'healthy' && (
                                  <span className="flex items-center gap-1 text-xs text-giga-success">
                                    <CheckCircle size={12} />
                                    Healthy
                                  </span>
                                )}
                                {gateway.health_status === 'unhealthy' && (
                                  <span className="flex items-center gap-1 text-xs text-giga-error">
                                    <XCircle size={12} />
                                    Unhealthy
                                  </span>
                                )}
                                {gateway.health_status === 'unknown' && (
                                  <span className="flex items-center gap-1 text-xs text-gray-400">
                                    <AlertCircle size={12} />
                                    Not tested
                                  </span>
                                )}
                              </div>
                              {gateway.last_error && (
                                <p className="text-xs text-giga-error mt-1">{gateway.last_error}</p>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => testGatewayMutation.mutate(gateway.id)}
                              disabled={testingGatewayId === gateway.id}
                              className="p-2 hover:bg-giga-card rounded-lg text-gray-400 hover:text-white transition-colors"
                              title="Test connection"
                            >
                              {testingGatewayId === gateway.id ? (
                                <Loader2 size={16} className="animate-spin" />
                              ) : (
                                <TestTube size={16} />
                              )}
                            </button>
                            {!gateway.is_primary && (
                              <button
                                onClick={() => handleSetPrimary(gateway.id)}
                                className="p-2 hover:bg-giga-card rounded-lg text-gray-400 hover:text-giga-accent transition-colors"
                                title="Set as primary"
                              >
                                <Star size={16} />
                              </button>
                            )}
                            <button
                              onClick={() => deleteGatewayMutation.mutate(gateway.id)}
                              className="p-2 hover:bg-giga-error/20 rounded-lg text-gray-400 hover:text-giga-error transition-colors"
                              title="Delete gateway"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                        
                        {/* Gateway actions row */}
                        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-sidebar-border/50">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={gateway.enabled}
                              onChange={() => handleToggleEnabled(gateway)}
                              className="rounded border-gray-600 bg-giga-card text-giga-accent focus:ring-giga-accent"
                            />
                            <span className="text-xs text-gray-400">Enabled</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={gateway.is_fallback}
                              onChange={() => handleToggleFallback(gateway)}
                              disabled={gateway.is_primary}
                              className="rounded border-gray-600 bg-giga-card text-giga-warning focus:ring-giga-warning disabled:opacity-50"
                            />
                            <span className="text-xs text-gray-400">Use as fallback</span>
                          </label>
                          <span className="text-xs text-gray-500">
                            Priority: {gateway.priority}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Add Gateway Modal */}
                {showAddGateway && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-giga-dark border border-sidebar-border rounded-xl p-6 w-full max-w-md">
                      <h3 className="text-lg font-semibold text-white mb-4">Add New Gateway</h3>
                      
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            Provider
                          </label>
                          <select
                            value={newGateway.provider}
                            onChange={(e) => setNewGateway({
                              ...newGateway,
                              provider: e.target.value as GatewayProvider,
                              name: newGateway.name || `${PROVIDER_INFO[e.target.value as GatewayProvider]?.name} Gateway`,
                            })}
                            className="input w-full"
                          >
                            {Object.entries(PROVIDER_INFO).map(([key, info]) => (
                              <option key={key} value={key}>
                                {info.icon} {info.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            Name
                          </label>
                          <input
                            type="text"
                            value={newGateway.name}
                            onChange={(e) => setNewGateway({ ...newGateway, name: e.target.value })}
                            placeholder="My Gateway"
                            className="input w-full"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            API Key
                          </label>
                          <input
                            type="password"
                            value={newGateway.api_key}
                            onChange={(e) => setNewGateway({ ...newGateway, api_key: e.target.value })}
                            placeholder="sk-..."
                            className="input w-full font-mono"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-gray-300 mb-2">
                            API Base URL (optional)
                          </label>
                          <input
                            type="text"
                            value={newGateway.api_base}
                            onChange={(e) => setNewGateway({ ...newGateway, api_base: e.target.value })}
                            placeholder="https://api.example.com/v1"
                            className="input w-full"
                          />
                        </div>
                        
                        <div className="flex items-center gap-4">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={newGateway.is_primary}
                              onChange={(e) => setNewGateway({ ...newGateway, is_primary: e.target.checked })}
                              className="rounded border-gray-600 bg-giga-card text-giga-accent"
                            />
                            <span className="text-sm text-gray-300">Set as primary</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={newGateway.is_fallback}
                              onChange={(e) => setNewGateway({ ...newGateway, is_fallback: e.target.checked })}
                              className="rounded border-gray-600 bg-giga-card text-giga-warning"
                            />
                            <span className="text-sm text-gray-300">Use as fallback</span>
                          </label>
                        </div>
                      </div>
                      
                      <div className="flex justify-end gap-3 mt-6">
                        <button
                          onClick={() => setShowAddGateway(false)}
                          className="btn-secondary"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => addGatewayMutation.mutate(newGateway)}
                          disabled={!newGateway.api_key || addGatewayMutation.isPending}
                          className="btn-primary flex items-center gap-2"
                        >
                          {addGatewayMutation.isPending ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Plus size={16} />
                          )}
                          Add Gateway
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Auth Token */}
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Authentication</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      <Key size={14} className="inline mr-2" />
                      API Token
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
                      This token is stored locally and used for API authentication
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

          {/* Providers Tab - Advanced only */}
          {activeTab === 'providers' && isAdvanced && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Provider API Keys</h3>
                <p className="text-xs text-gray-500 mb-4">Configure API keys for each provider individually</p>
                <div className="space-y-4">
                  {Object.entries(PROVIDER_INFO).map(([key, info]) => (
                    <div key={key} className="p-4 bg-giga-hover rounded-lg">
                      <div className="flex items-center gap-3 mb-3">
                        <span className="text-xl">{info.icon}</span>
                        <span className={cn('font-medium', info.color)}>{info.name}</span>
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="password"
                          placeholder={`${info.name} API Key...`}
                          className="input flex-1 font-mono text-sm"
                        />
                        <button className="btn-secondary">
                          <Save size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
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
                    { tier: 'Tier 1', description: 'Most capable, used for complex reasoning', color: 'purple' },
                    { tier: 'Tier 2', description: 'Balanced performance and cost', color: 'blue' },
                    { tier: 'Tier 3', description: 'Fast responses, lower cost', color: 'green' },
                  ].map((t) => (
                    <div key={t.tier} className={cn('p-4 rounded-lg border', `border-${t.color}-500/30 bg-${t.color}-500/10`)}>
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className={`font-medium text-${t.color}-400`}>{t.tier}</h4>
                          <p className="text-xs text-gray-500">{t.description}</p>
                        </div>
                      </div>
                      <select className="input w-full">
                        <option>gpt-4-turbo (OpenAI)</option>
                        <option>claude-3-opus (Anthropic)</option>
                        <option>gpt-4 (OpenAI)</option>
                        <option>claude-3-sonnet (Anthropic)</option>
                        <option>gpt-3.5-turbo (OpenAI)</option>
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
                    <div className="w-12 h-6 rounded-full bg-giga-success relative">
                      <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white" />
                    </div>
                  </label>
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Fallback on Error</p>
                      <p className="text-xs text-gray-500">Try next tier if current tier fails</p>
                    </div>
                    <div className="w-12 h-6 rounded-full bg-giga-success relative">
                      <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white" />
                    </div>
                  </label>
                </div>
              </div>
            </>
          )}

          {/* Memory Tab - Advanced only */}
          {activeTab === 'memory' && isAdvanced && (
            <>
              <div className="card">
                <h3 className="font-semibold text-white mb-4">Memory Configuration</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between py-2 border-b border-sidebar-border">
                    <div>
                      <p className="text-sm text-gray-300">Vector Store</p>
                      <p className="text-xs text-gray-500">Storage backend for embeddings</p>
                    </div>
                    <select className="input w-40">
                      <option>ChromaDB</option>
                      <option>Pinecone</option>
                      <option>Weaviate</option>
                      <option>FAISS</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between py-2 border-b border-sidebar-border">
                    <div>
                      <p className="text-sm text-gray-300">Chunk Size</p>
                      <p className="text-xs text-gray-500">Size of text chunks for embedding</p>
                    </div>
                    <input type="number" defaultValue={512} className="input w-24 text-center" />
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-sm text-gray-300">Top K Results</p>
                      <p className="text-xs text-gray-500">Number of results to retrieve</p>
                    </div>
                    <input type="number" defaultValue={5} className="input w-24 text-center" />
                  </div>
                </div>
              </div>

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
                <h3 className="font-semibold text-white mb-4">Team Role Configuration</h3>
                <p className="text-xs text-gray-500 mb-4">Configure model assignments for each team role</p>
                
                <div className="space-y-4">
                  {[
                    { role: 'Lead', description: 'Coordinates and makes final decisions', icon: '👑' },
                    { role: 'Researcher', description: 'Gathers and analyzes information', icon: '🔍' },
                    { role: 'Coder', description: 'Implements solutions', icon: '💻' },
                    { role: 'Reviewer', description: 'Reviews and provides feedback', icon: '✅' },
                  ].map((r) => (
                    <div key={r.role} className="p-4 bg-giga-hover rounded-lg">
                      <div className="flex items-center gap-3 mb-3">
                        <span className="text-xl">{r.icon}</span>
                        <div>
                          <h4 className="font-medium text-white">{r.role}</h4>
                          <p className="text-xs text-gray-500">{r.description}</p>
                        </div>
                      </div>
                      <select className="input w-full">
                        <option>gpt-4-turbo</option>
                        <option>claude-3-opus</option>
                        <option>gpt-4</option>
                        <option>claude-3-sonnet</option>
                      </select>
                    </div>
                  ))}
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
                    <div className="w-12 h-6 rounded-full bg-giga-success relative">
                      <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white" />
                    </div>
                  </label>
                  <label className="flex items-center justify-between p-3 bg-giga-hover rounded-lg cursor-pointer">
                    <div>
                      <p className="text-sm text-gray-300">Security Audit</p>
                      <p className="text-xs text-gray-500">Run security checks on all outputs</p>
                    </div>
                    <div className="w-12 h-6 rounded-full bg-giga-success relative">
                      <span className="absolute right-1 top-1 w-4 h-4 rounded-full bg-white" />
                    </div>
                  </label>
                </div>
              </div>
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
