import { useState, useCallback } from 'react'
import { useSystem } from '@/contexts/SystemContext'
import { useToast } from '@/components/ui/Toast'
import { Check, X, Loader2, Eye, EyeOff, ExternalLink, RefreshCw } from 'lucide-react'

/**
 * Provider configuration type.
 */
interface ProviderConfig {
  id: string
  name: string
  icon: string
  description: string
  docsUrl: string
  placeholder: string
}

/**
 * Available providers.
 */
const PROVIDERS: ProviderConfig[] = [
  {
    id: 'openrouter',
    name: 'OpenRouter',
    icon: '🌐',
    description: 'Access 100+ models through a single API',
    docsUrl: 'https://openrouter.ai/keys',
    placeholder: 'sk-or-...',
  },
  {
    id: 'anthropic',
    name: 'Anthropic (Claude)',
    icon: '🧠',
    description: 'Claude models for advanced reasoning',
    docsUrl: 'https://console.anthropic.com/',
    placeholder: 'sk-ant-...',
  },
  {
    id: 'openai',
    name: 'OpenAI (GPT)',
    icon: '⚡',
    description: 'GPT-4 and other OpenAI models',
    docsUrl: 'https://platform.openai.com/api-keys',
    placeholder: 'sk-...',
  },
  {
    id: 'moonshot',
    name: 'Moonshot (Kimi)',
    icon: '🌙',
    description: 'Kimi models with long context support',
    docsUrl: 'https://platform.moonshot.cn/',
    placeholder: 'sk-...',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    icon: '🔍',
    description: 'DeepSeek models for coding and reasoning',
    docsUrl: 'https://platform.deepseek.com/',
    placeholder: 'sk-...',
  },
]

/**
 * Provider card component.
 */
function ProviderCard({
  provider,
  configured,
  isPrimary,
  onSave,
  onTest,
  saving,
  testing,
}: {
  provider: ProviderConfig
  configured: boolean
  isPrimary: boolean
  onSave: (apiKey: string) => Promise<void>
  onTest: () => Promise<void>
  saving: boolean
  testing: boolean
}) {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [dirty, setDirty] = useState(false)

  const handleSave = async () => {
    if (!apiKey.trim()) return
    await onSave(apiKey)
    setApiKey('')
    setDirty(false)
  }

  const handleKeyChange = (value: string) => {
    setApiKey(value)
    setDirty(true)
  }

  return (
    <div className={`bg-giga-darker border rounded-xl p-5 ${configured ? 'border-green-500/50' : 'border-giga-border'}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{provider.icon}</span>
          <div>
            <h3 className="font-semibold text-white">{provider.name}</h3>
            <p className="text-sm text-gray-500">{provider.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {configured && (
            <span className={`text-xs px-2 py-1 rounded-full ${isPrimary ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
              {isPrimary ? 'Primary' : 'Configured'}
            </span>
          )}
        </div>
      </div>

      <div className="space-y-3">
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => handleKeyChange(e.target.value)}
            placeholder={configured ? '••••••••••••••••' : provider.placeholder}
            className="w-full px-4 py-3 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 pr-10 focus:outline-none focus:border-giga-accent"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={!dirty || !apiKey.trim() || saving}
            className="px-4 py-2 bg-giga-accent text-white rounded-lg font-medium hover:bg-giga-accent/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save'
            )}
          </button>
          
          {configured && (
            <button
              onClick={onTest}
              disabled={testing}
              className="px-4 py-2 bg-giga-dark border border-giga-border text-white rounded-lg font-medium hover:bg-giga-darker flex items-center gap-2"
            >
              {testing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Test
                </>
              )}
            </button>
          )}
          
          <a
            href={provider.docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 text-gray-400 hover:text-white flex items-center gap-1"
          >
            Get API Key <ExternalLink size={14} />
          </a>
        </div>
      </div>
    </div>
  )
}

/**
 * ProvidersTab component.
 * 
 * Shows all available providers with their configuration status
 * and allows updating API keys with live reinitialize.
 */
export function ProvidersTab() {
  const { configuredProviders, primaryProvider, reinitialize, agentState } = useSystem()
  const toast = useToast()
  const [savingProvider, setSavingProvider] = useState<string | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)

  const handleSaveProvider = useCallback(async (providerId: string, apiKey: string) => {
    setSavingProvider(providerId)
    try {
      const res = await fetch(`/api/providers/${providerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      })
      
      const data = await res.json()
      
      if (data.success) {
        toast.success(`${providerId} API key saved successfully!`)
      } else {
        toast.error(data.message || 'Failed to save API key')
      }
    } catch (error) {
      toast.error('Failed to save API key')
    } finally {
      setSavingProvider(null)
    }
  }, [toast])

  const handleTestProvider = useCallback(async (providerId: string) => {
    setTestingProvider(providerId)
    try {
      const res = await fetch(`/api/providers/${providerId}/test`, {
        method: 'POST',
      })
      
      const data = await res.json()
      
      if (data.success) {
        toast.success(`${providerId} connection successful!`)
      } else {
        toast.error(data.error || 'Connection test failed')
      }
    } catch (error) {
      toast.error('Connection test failed')
    } finally {
      setTestingProvider(null)
    }
  }, [toast])

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div className={`p-4 rounded-lg ${agentState === 'ready' ? 'bg-green-500/10 border border-green-500/30' : 'bg-yellow-500/10 border border-yellow-500/30'}`}>
        <div className="flex items-center gap-3">
          {agentState === 'ready' ? (
            <>
              <Check className="w-5 h-5 text-green-500" />
              <div>
                <p className="font-medium text-green-400">Agent Ready</p>
                <p className="text-sm text-green-400/70">
                  Using {primaryProvider || 'default'} as primary provider. Chat is enabled.
                </p>
              </div>
            </>
          ) : (
            <>
              <X className="w-5 h-5 text-yellow-500" />
              <div>
                <p className="font-medium text-yellow-400">Agent Not Ready</p>
                <p className="text-sm text-yellow-400/70">
                  Configure at least one provider below to enable chat.
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Provider Cards */}
      <div className="space-y-4">
        <h3 className="text-lg font-medium text-white">LLM Providers</h3>
        <p className="text-sm text-gray-400">
          Configure your API keys below. Changes are applied immediately without restart.
        </p>
        
        {PROVIDERS.map((provider) => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            configured={configuredProviders.includes(provider.id)}
            isPrimary={primaryProvider === provider.id}
            onSave={(apiKey) => handleSaveProvider(provider.id, apiKey)}
            onTest={() => handleTestProvider(provider.id)}
            saving={savingProvider === provider.id}
            testing={testingProvider === provider.id}
          />
        ))}
      </div>
    </div>
  )
}

export default ProvidersTab
