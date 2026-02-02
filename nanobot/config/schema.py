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


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    tiered_routing: TieredRoutingConfig = Field(default_factory=TieredRoutingConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)
    team: TeamConfig = Field(default_factory=TeamConfig)
    dev_workflow: DevWorkflowConfig = Field(default_factory=DevWorkflowConfig)


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
    password_hash: str = ""  # SHA-256 hash for password mode
    tailscale_required_user: str = ""  # For tailscale mode
    paired_devices: list[str] = Field(default_factory=list)
    require_pairing: bool = False


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
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def get_api_key(self, provider: str | None = None) -> str | None:
        """
        Get API key for a specific provider or in priority order.
        
        Args:
            provider: Specific provider name, or None for auto-detect.
        
        Returns:
            API key string or None.
        """
        if provider:
            provider_config = getattr(self.providers, provider, None)
            if provider_config:
                return provider_config.api_key or None
        
        # Priority order: OpenRouter > Anthropic > OpenAI > Moonshot > DeepSeek > vLLM
        return (
            self.providers.openrouter.api_key or
            self.providers.anthropic.api_key or
            self.providers.openai.api_key or
            self.providers.moonshot.api_key or
            self.providers.deepseek.api_key or
            self.providers.vllm.api_key or
            None
        )
    
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
