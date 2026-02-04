// API Response Types

export interface StatusResponse {
  status: string
  version: string
  model?: string
  workspace?: string
  channels?: Record<string, ChannelStatus>
  tracking?: TrackingStats
}

export interface TrackingStats {
  session?: {
    total_tokens: number
    prompt_tokens: number
    completion_tokens: number
    estimated_cost: number
  }
  efficiency_score?: number
}

export interface ChannelStatus {
  enabled: boolean
  running: boolean
  connected?: boolean
  error?: string
}

export interface Session {
  key: string
  message_count: number
  last_updated?: string
  channel?: string
  user?: string
}

export interface Conversation {
  id: string
  channel: ChannelType
  user: {
    id: string
    name: string
    avatar?: string
  }
  lastMessage?: {
    content: string
    timestamp: string
    isFromBot: boolean
  }
  unreadCount: number
  status: 'open' | 'closed' | 'pending'
}

export interface Message {
  id: string
  content: string
  timestamp: string
  role: 'user' | 'assistant' | 'system'
  toolCalls?: ToolCall[]
  status?: 'sending' | 'sent' | 'error'
}

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: string
  status: 'pending' | 'running' | 'completed' | 'error'
}

export type ChannelType = 
  | 'whatsapp' 
  | 'telegram' 
  | 'discord' 
  | 'slack' 
  | 'signal' 
  | 'matrix' 
  | 'web' 
  | 'sms'

export interface ChannelConfig {
  type: ChannelType
  enabled: boolean
  config: Record<string, unknown>
}

// WebSocket Event Types

export type WebSocketEvent =
  | { type: 'connected' }
  | { type: 'disconnected' }
  | { type: 'status'; data: StatusResponse }
  | { type: 'typing'; status: boolean }
  | { type: 'response'; content: string; session_id: string }
  | { type: 'error'; error: string }
  | { type: 'pong' }
  | { type: 'dashboard:building'; progress: number }
  | { type: 'dashboard:ready'; version: string }
  | { type: 'dashboard:refresh' }

export type WebSocketAction =
  | { action: 'chat'; message: string; session_id?: string; model?: string; thinking_level?: 'low' | 'medium' | 'high' }
  | { action: 'ping' }
  | { action: 'status' }
  | { action: 'abort'; session_id?: string }

// Config Types

export interface GigaBotConfig {
  agents: {
    model: string
    max_tokens: number
    tiered_routing: boolean
  }
  channels: Record<string, { enabled: boolean }>
  security: {
    auth_mode: string
    sandbox_mode: string
  }
}

// Dashboard Version Types

export interface DashboardVersion {
  version: string
  created_at: string
  is_current: boolean
  size_bytes: number
}

// Gateway Types

export interface Gateway {
  id: string
  name: string
  provider: GatewayProvider
  enabled: boolean
  is_primary: boolean
  is_fallback: boolean
  priority: number
  health_status: 'healthy' | 'unhealthy' | 'unknown'
  last_error: string | null
  failure_count: number
  has_api_key: boolean
  api_base: string | null
}

export type GatewayProvider = 
  | 'openrouter'
  | 'anthropic'
  | 'openai'
  | 'moonshot'
  | 'deepseek'
  | 'glm'
  | 'qwen'
  | 'ollama'
  | 'vllm'

export interface GatewaysResponse {
  gateways: Gateway[]
  cooldown_seconds: number
  max_retries: number
}

export interface GatewayTestResult {
  success: boolean
  status: 'healthy' | 'unhealthy'
  message?: string
  error?: string
}

// Provider Configuration Types

export interface ProviderInfo {
  has_key: boolean
  api_base: string | null
  enabled: boolean
}

export interface ProvidersResponse {
  providers: Record<GatewayProvider, ProviderInfo>
}

// Routing Configuration Types

export interface TierConfig {
  models: string[]
  triggers: string[]
}

export interface RoutingConfig {
  enabled: boolean
  fallback_tier: string
  tiers: Record<string, TierConfig>
}

// Memory Configuration Types

export interface MemoryConfig {
  enabled: boolean
  vector_search: boolean
  context_memories: number
}

// Team Configuration Types

export interface TeamConfig {
  enabled: boolean
  qa_gate_enabled: boolean
  audit_gate_enabled: boolean
  audit_threshold: string
}

export interface SwarmConfig {
  enabled: boolean
  max_workers: number
  worker_model: string
  orchestrator_model: string
}

export interface TeamConfigResponse {
  team: TeamConfig
  swarm: SwarmConfig
}
