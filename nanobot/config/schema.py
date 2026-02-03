"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames


class DiscordConfig(BaseModel):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    application_id: str = ""  # Application ID
    allow_guilds: list[str] = Field(default_factory=list)  # Allowed guild IDs
    allow_channels: list[str] = Field(default_factory=list)  # Allowed channel IDs
    allow_users: list[str] = Field(default_factory=list)  # Allowed user IDs


class SignalConfig(BaseModel):
    """Signal channel configuration."""
    enabled: bool = False
    phone_number: str = ""  # Signal phone number
    signal_cli_path: str = "signal-cli"  # Path to signal-cli
    config_path: str = ""  # Signal CLI config directory
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class MatrixConfig(BaseModel):
    """Matrix channel configuration."""
    enabled: bool = False
    homeserver: str = ""  # Matrix homeserver URL
    user_id: str = ""  # Bot user ID (@bot:server.com)
    access_token: str = ""  # Access token (or use password)
    password: str = ""  # Password (alternative to access_token)
    device_id: str = ""  # Device ID for E2EE
    enable_encryption: bool = False  # Enable E2EE
    allow_rooms: list[str] = Field(default_factory=list)  # Allowed room IDs


class SlackConfig(BaseModel):
    """Slack channel configuration."""
    enabled: bool = False
    bot_token: str = ""  # Bot User OAuth Token (xoxb-...)
    app_token: str = ""  # App-Level Token for Socket Mode (xapp-...)
    signing_secret: str = ""  # Signing secret for verification
    allow_channels: list[str] = Field(default_factory=list)  # Allowed channel IDs
    allow_users: list[str] = Field(default_factory=list)  # Allowed user IDs


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    signal: SignalConfig = Field(default_factory=SignalConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class TierConfig(BaseModel):
    """Configuration for a model tier."""
    models: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)


class TieredRoutingConfig(BaseModel):
    """Tiered model routing configuration."""
    enabled: bool = False
    tiers: dict[str, TierConfig] = Field(default_factory=lambda: {
        "daily_driver": TierConfig(
            models=["moonshot/kimi-k2.5", "google/gemini-2.0-flash"],
            triggers=["chat", "simple_query", "task_management"]
        ),
        "coder": TierConfig(
            models=["anthropic/claude-sonnet-4-5", "openai/gpt-4.1"],
            triggers=["code", "debug", "implement", "refactor"]
        ),
        "specialist": TierConfig(
            models=["anthropic/claude-opus-4-5", "google/gemini-2.0-pro"],
            triggers=["brainstorm", "creative", "complex_analysis", "research"]
        ),
    })
    classifier_model: str = ""  # Lightweight model for classification
    fallback_tier: str = "daily_driver"


class SwarmConfig(BaseModel):
    """Swarm system configuration."""
    enabled: bool = False
    max_workers: int = 5
    worker_model: str = "moonshot/kimi-k2.5"
    orchestrator_model: str = "anthropic/claude-sonnet-4-5"
    auto_trigger: bool = True  # Auto-detect when to use swarm
    complexity_threshold: int = 3  # Score threshold for auto-swarm
    patterns: dict[str, list[str]] = Field(default_factory=lambda: {
        "research": ["search", "summarize", "report"],
        "code": ["implement", "test", "refactor"],
        "review": ["analyze", "critique", "suggest"],
        "brainstorm": ["generate", "evaluate", "develop"],
    })


class VisualValidationConfig(BaseModel):
    """Visual validation configuration for Kimi-style screenshot analysis."""
    enabled: bool = False
    vision_model: str = "anthropic/claude-sonnet-4-5"
    auto_screenshot: bool = True
    max_fix_iterations: int = 5
    screenshot_delay_ms: int = 2000  # Wait before taking screenshot


class DevWorkflowConfig(BaseModel):
    """Agentic development workflow configuration."""
    enabled: bool = False
    default_port: int = 3000
    dev_command: str = "npm run dev"
    ready_pattern: str = "ready|listening|started|compiled|Local:"
    server_timeout: int = 30  # Seconds to wait for dev server ready
    visual_validation: VisualValidationConfig = Field(default_factory=VisualValidationConfig)


class AgentRoleConfig(BaseModel):
    """Configuration for a single agent role in the team."""
    enabled: bool = True
    model: str = ""  # Empty means use default for role
    temperature: float = 0.7
    max_tokens: int = 4096
    custom_persona: str = ""  # Override default persona


class TeamConfig(BaseModel):
    """Agent team configuration for persona-based hierarchy."""
    enabled: bool = False
    
    # Role configurations (override defaults)
    roles: dict[str, AgentRoleConfig] = Field(default_factory=lambda: {
        "architect": AgentRoleConfig(model="anthropic/claude-opus-4-5"),
        "lead_dev": AgentRoleConfig(model="anthropic/claude-sonnet-4-5"),
        "senior_dev": AgentRoleConfig(model="moonshot/kimi-k2.5"),
        "junior_dev": AgentRoleConfig(model="google/gemini-2.0-flash"),
        "qa_engineer": AgentRoleConfig(model="anthropic/claude-sonnet-4-5"),
        "auditor": AgentRoleConfig(model="anthropic/claude-opus-4-5"),
        "researcher": AgentRoleConfig(model="google/gemini-2.0-flash"),
    })
    
    # Quality gates
    qa_gate_enabled: bool = True
    audit_gate_enabled: bool = True
    audit_threshold: str = "sensitive"  # "all", "sensitive", "none"
    
    # Deliberation settings
    deliberation_timeout: int = 120  # Seconds to wait for opinions
    min_opinions: int = 3  # Minimum opinions to gather


class ProfilerConfig(BaseModel):
    """Model profiler configuration for HR-style model interviews."""
    enabled: bool = True
    
    # Interviewer settings
    interviewer_model: str = "anthropic/claude-opus-4-5"  # High-reasoning model for evaluation
    
    # Auto-interview settings
    auto_interview: bool = True  # Interview unknown models automatically
    profile_max_age_days: int = 30  # Re-interview after this many days
    quick_assess_on_failure: bool = True  # Quick re-assess after failures
    
    # Storage
    storage_path: str = "~/.gigabot/profiles"  # Where to store profiles
    
    # Test settings
    test_timeout: int = 30  # Timeout per test in seconds
    quick_test_categories: list[str] = Field(default_factory=lambda: [
        "tool_calling",
        "instruction",
        "reasoning",
    ])
    
    # Integration settings
    validate_role_assignments: bool = True  # Warn if model unsuited for role
    apply_guardrails: bool = True  # Apply profile-based guardrails to prompts


class MemoryConfig(BaseModel):
    """Deep memory system configuration."""
    enabled: bool = True
    
    # Vector search settings
    vector_search: bool = True  # Enable semantic memory retrieval
    context_memories: int = 5  # Number of relevant memories to include in context
    
    # Auto-extraction settings
    auto_extract_facts: bool = True  # Extract and store important facts from conversations
    save_compaction_summaries: bool = True  # Save conversation summaries to memory
    
    # Storage settings
    storage_path: str = "~/.gigabot/memory"  # Where to store memory data
    vector_dimension: int = 384  # Embedding dimension (384 for MiniLM)
    
    # Search weights
    vector_weight: float = 0.6  # Weight for semantic similarity
    keyword_weight: float = 0.3  # Weight for keyword matching
    recency_weight: float = 0.1  # Weight for recency
    recency_days: int = 30  # Days to consider for recency scoring


class SelfHealConfig(BaseModel):
    """Self-healing controls configuration."""
    enabled: bool = True
    
    # Tool retry settings
    tool_retry_enabled: bool = True
    max_tool_retries: int = 3
    retry_base_delay: float = 1.0  # Initial delay in seconds
    retry_max_delay: float = 30.0  # Maximum delay
    retry_exponential_base: float = 2.0  # Backoff multiplier
    
    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5  # Failures before opening circuit
    circuit_breaker_cooldown: int = 300  # Seconds before reset (5 min)
    
    # Swarm retry settings
    swarm_task_retry: bool = True
    swarm_max_retries: int = 2
    
    # Error pattern learning
    track_error_patterns: bool = True
    error_pattern_threshold: int = 3  # Occurrences before flagging


class ToolReinforcementConfig(BaseModel):
    """Agentic tool calling reinforcement configuration."""
    enabled: bool = True
    
    # Pre-execution validation
    pre_validation: bool = True  # Validate parameters before execution
    enforce_security_policy: bool = True  # Check tool policy before execution
    
    # Adaptive tool selection
    adaptive_selection: bool = True  # Track and learn from tool usage
    track_model_tool_performance: bool = True  # Per-model tool success rates
    
    # Profiler feedback
    feedback_to_profiler: bool = True  # Update model profiles from tool calls
    feedback_interval: int = 100  # Update profile every N calls
    
    # Advisor thresholds (configurable)
    min_calls_for_confidence: int = 5  # Min calls before using actual success rate
    default_confidence: float = 0.7  # Confidence when not enough data
    error_warning_threshold: int = 3  # Error count before warning
    suggest_alternative_threshold: float = 0.5  # Confidence below this suggests alternative
    
    # Storage
    advisor_storage_path: str = "~/.gigabot/tool_advisor.json"


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    tiered_routing: TieredRoutingConfig = Field(default_factory=TieredRoutingConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)
    team: TeamConfig = Field(default_factory=TeamConfig)
    profiler: ProfilerConfig = Field(default_factory=ProfilerConfig)
    dev_workflow: DevWorkflowConfig = Field(default_factory=DevWorkflowConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    self_heal: SelfHealConfig = Field(default_factory=SelfHealConfig)
    tool_reinforcement: ToolReinforcementConfig = Field(default_factory=ToolReinforcementConfig)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None
    auth_type: Literal["api-key", "oauth", "aws-sdk"] = "api-key"
    api_format: Literal["openai", "anthropic", "google"] = "openai"


class ModelFallbackConfig(BaseModel):
    """Model failover configuration."""
    primary: str = ""
    fallbacks: list[str] = Field(default_factory=list)
    cooldown_seconds: int = 300  # Time before retrying failed provider


class LLMGatewayConfig(BaseModel):
    """Individual LLM gateway configuration for multi-gateway support."""
    id: str = ""  # Unique identifier
    name: str = ""  # Display name
    provider: Literal[
        "openrouter", "anthropic", "openai", "moonshot", 
        "deepseek", "glm", "qwen", "ollama", "vllm"
    ] = "openrouter"
    api_key: str = ""
    api_base: str | None = None
    enabled: bool = False
    is_primary: bool = False
    is_fallback: bool = False
    priority: int = 0  # Lower = higher priority for fallbacks
    health_status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    last_error: str | None = None
    failure_count: int = 0


class LLMGatewaysConfig(BaseModel):
    """Multi-gateway configuration with fallback support."""
    gateways: list[LLMGatewayConfig] = Field(default_factory=list)
    cooldown_seconds: int = 300  # Time before retrying failed gateway
    max_retries: int = 3  # Max retries per gateway before moving to next


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=lambda: ProviderConfig(
        api_base="https://api.moonshot.cn/v1"
    ))
    glm: ProviderConfig = Field(default_factory=lambda: ProviderConfig(
        api_base="https://open.bigmodel.cn/api/paas/v4"
    ))
    deepseek: ProviderConfig = Field(default_factory=lambda: ProviderConfig(
        api_base="https://api.deepseek.com/v1"
    ))
    qwen: ProviderConfig = Field(default_factory=lambda: ProviderConfig(
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        auth_type="oauth"
    ))
    ollama: ProviderConfig = Field(default_factory=lambda: ProviderConfig(
        api_base="http://localhost:11434/v1"
    ))
    
    # Model failover configuration
    failover: ModelFallbackConfig = Field(default_factory=ModelFallbackConfig)
    
    # Multi-gateway configuration with fallback
    gateways: LLMGatewaysConfig = Field(default_factory=LLMGatewaysConfig)


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790
    websocket_port: int = 18791  # WebSocket server for real-time
    enable_http_api: bool = True
    enable_websocket: bool = True


# Security configuration classes
class AuthConfig(BaseModel):
    """Authentication configuration."""
    mode: Literal["none", "token", "password", "tailscale"] = "none"
    token: str = ""  # For token mode
    password_hash: str = ""  # SHA-256 hash for password mode (with salt)
    password_salt: str = ""  # Salt for password hashing
    pin_hash: str = ""  # SHA-256 hash for PIN (with salt)
    pin_salt: str = ""  # Salt for PIN hashing
    require_pin: bool = True  # Require PIN after password (two-factor)
    session_duration_days: int = 7  # Cookie session duration
    tailscale_required_user: str = ""  # For tailscale mode
    paired_devices: list[str] = Field(default_factory=list)
    require_pairing: bool = False
    setup_complete: bool = False  # True once password/PIN initially configured


class ToolPolicyConfig(BaseModel):
    """Tool access policy configuration."""
    allow: list[str] = Field(default_factory=lambda: ["*"])
    deny: list[str] = Field(default_factory=list)
    require_approval: list[str] = Field(default_factory=list)
    require_elevated: list[str] = Field(default_factory=lambda: ["gateway"])


class DockerSandboxConfig(BaseModel):
    """Docker sandbox configuration."""
    image: str = "debian:bookworm-slim"
    read_only_root: bool = True
    network: str = "none"
    cap_drop: list[str] = Field(default_factory=lambda: ["ALL"])
    tmpfs: list[str] = Field(default_factory=lambda: ["/tmp", "/var/tmp", "/run"])
    pids_limit: int = 100
    memory: str = "512m"


class SandboxConfig(BaseModel):
    """Sandbox configuration."""
    mode: Literal["off", "non-main", "all"] = "off"
    scope: Literal["shared", "agent", "session"] = "session"
    workspace_access: Literal["none", "ro", "rw"] = "ro"
    docker: DockerSandboxConfig = Field(default_factory=DockerSandboxConfig)


class EncryptionConfig(BaseModel):
    """Encryption configuration."""
    encrypt_config: bool = False  # Encrypt config at rest
    encrypt_memory: bool = False  # Encrypt memory files
    encrypt_sessions: bool = False  # Encrypt session transcripts


class SecurityConfig(BaseModel):
    """Security configuration."""
    auth: AuthConfig = Field(default_factory=AuthConfig)
    tool_policy: ToolPolicyConfig = Field(default_factory=ToolPolicyConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)


class HeartbeatConfig(BaseModel):
    """Heartbeat service configuration."""
    enabled: bool = True
    every_seconds: int = 1800  # 30 minutes


class TokenTrackingConfig(BaseModel):
    """Token usage tracking configuration."""
    enabled: bool = True
    daily_budget: int = 0  # 0 = unlimited
    weekly_budget: int = 0
    alert_threshold: float = 0.8  # Alert at 80% of budget


class NodesConfig(BaseModel):
    """Node system configuration for remote command execution."""
    enabled: bool = False  # Enable node system
    auth_token: str = ""  # Token for node authentication
    auto_approve: bool = False  # Auto-approve new nodes
    ping_interval: int = 30  # Seconds between health check pings
    storage_path: str = "~/.gigabot/nodes.json"  # Node registry storage


class ExecConfig(BaseModel):
    """Exec tool configuration with node routing."""
    host: Literal["local", "node"] = "local"  # Default execution host
    node: str = ""  # Default node ID or name for remote execution
    fallback_to_local: bool = True  # Fallback to local if node unavailable
    timeout: int = 60  # Default timeout in seconds
    
    # Node-local exec approvals (when running as node host)
    allow_by_default: bool = False  # Allow commands not in allowlist
    use_default_safe: bool = True  # Include default safe command patterns
    use_default_deny: bool = True  # Include default dangerous command patterns


class Config(BaseSettings):
    """Root configuration for nanobot/GigaBot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    tracking: TokenTrackingConfig = Field(default_factory=TokenTrackingConfig)
    nodes: NodesConfig = Field(default_factory=NodesConfig)
    exec: ExecConfig = Field(default_factory=ExecConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def get_api_key(self, provider: str | None = None) -> str | None:
        """
        Get API key for a specific provider or in priority order.
        
        Checks both config and environment variables.
        
        Args:
            provider: Specific provider name, or None for auto-detect.
        
        Returns:
            API key string or None.
        """
        import os
        
        # Map of provider names to environment variable names
        env_vars = {
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "glm": "GLM_API_KEY",
            "qwen": "QWEN_API_KEY",
        }
        
        if provider:
            provider_config = getattr(self.providers, provider, None)
            if provider_config and provider_config.api_key:
                return provider_config.api_key
            # Check environment variable
            env_var = env_vars.get(provider, "")
            if env_var:
                return os.environ.get(env_var) or None
            return None
        
        # Priority order: OpenRouter > Anthropic > OpenAI > Moonshot > DeepSeek > vLLM
        # Check config first, then environment variables
        for prov, env_var in env_vars.items():
            provider_config = getattr(self.providers, prov, None)
            if provider_config and provider_config.api_key:
                return provider_config.api_key
            if os.environ.get(env_var):
                return os.environ.get(env_var)
        
        # Check vLLM last (no env var typically)
        if self.providers.vllm.api_key:
            return self.providers.vllm.api_key
        
        return None
    
    def get_api_base(self, provider: str | None = None) -> str | None:
        """
        Get API base URL for a specific provider or auto-detect.
        
        Args:
            provider: Specific provider name, or None for auto-detect.
        
        Returns:
            API base URL or None.
        """
        if provider:
            provider_config = getattr(self.providers, provider, None)
            if provider_config and provider_config.api_base:
                return provider_config.api_base
        
        if self.providers.openrouter.api_key:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if self.providers.moonshot.api_key:
            return self.providers.moonshot.api_base
        if self.providers.deepseek.api_key:
            return self.providers.deepseek.api_base
        if self.providers.vllm.api_base:
            return self.providers.vllm.api_base
        return None
    
    def get_provider_for_model(self, model: str) -> str | None:
        """
        Determine which provider to use for a given model.
        
        Args:
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
        
        Returns:
            Provider name or None.
        """
        model_lower = model.lower()
        
        if model_lower.startswith("moonshot/") or "kimi" in model_lower:
            return "moonshot"
        if model_lower.startswith("glm/") or "zhipu" in model_lower:
            return "glm"
        if model_lower.startswith("qwen/"):
            return "qwen"
        if model_lower.startswith("deepseek/"):
            return "deepseek"
        if model_lower.startswith("ollama/"):
            return "ollama"
        if model_lower.startswith("anthropic/") or "claude" in model_lower:
            return "anthropic"
        if model_lower.startswith("openai/") or "gpt" in model_lower:
            return "openai"
        
        # Default to OpenRouter for unknown models
        if self.providers.openrouter.api_key:
            return "openrouter"
        
        return None
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
