"""
Agent lifecycle manager with hot-reload support.

Provides:
- State machine for agent lifecycle (uninitialized -> ready)
- Hot-reload when config changes
- Thread-safe initialization with asyncio.Lock
"""

import asyncio
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from datetime import datetime

from loguru import logger

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.tracking.tokens import TokenTracker
    from nanobot.session.manager import SessionManager


class AgentState(Enum):
    """Agent lifecycle states."""
    UNINITIALIZED = "uninitialized"  # No API key configured
    INITIALIZING = "initializing"    # Creating AgentLoop
    READY = "ready"                  # Agent functional
    ERROR = "error"                  # Initialization failed


class AgentManager:
    """
    Manages AgentLoop lifecycle with hot-reload support.
    
    Features:
    - State machine for agent lifecycle
    - Hot-reload when API keys change
    - Thread-safe initialization
    - Error tracking and recovery
    """
    
    def __init__(
        self,
        config: "Config",
        workspace: Path,
        bus: "MessageBus | None" = None,
    ):
        self._config = config
        self._workspace = workspace
        self._bus = bus
        
        # Agent instance
        self._agent: "AgentLoop | None" = None
        
        # State tracking
        self._state = AgentState.UNINITIALIZED
        self._error: str | None = None
        self._initialized_at: datetime | None = None
        self._last_reinit_at: datetime | None = None
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        # Dependencies (created during initialization)
        self._provider = None
        self._tracker: "TokenTracker | None" = None
        self._sessions: "SessionManager | None" = None
    
    @property
    def state(self) -> AgentState:
        """Current agent state."""
        return self._state
    
    @property
    def is_ready(self) -> bool:
        """Check if agent is ready to handle requests."""
        return self._state == AgentState.READY
    
    @property
    def agent(self) -> "AgentLoop | None":
        """Get the agent loop instance (may be None)."""
        return self._agent
    
    @property
    def tracker(self) -> "TokenTracker | None":
        """Get the token tracker instance."""
        return self._tracker
    
    @property
    def sessions(self) -> "SessionManager | None":
        """Get the session manager instance."""
        return self._sessions
    
    @property
    def error(self) -> str | None:
        """Get the last error message."""
        return self._error
    
    def get_status(self) -> dict[str, Any]:
        """Get comprehensive status information."""
        return {
            "agent_state": self._state.value,
            "is_ready": self.is_ready,
            "error": self._error,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "last_reinit_at": self._last_reinit_at.isoformat() if self._last_reinit_at else None,
            "has_api_key": self._has_api_key(),
            "configured_providers": self._get_configured_providers(),
            "primary_provider": self._get_primary_provider(),
            "version": "0.1.0",
        }
    
    def get_not_ready_message(self) -> str:
        """Get a user-friendly message explaining why agent is not ready."""
        if self._state == AgentState.UNINITIALIZED:
            return "Chat is disabled - no API key configured. Go to Settings > Providers and enter your API key."
        elif self._state == AgentState.INITIALIZING:
            return "Agent is initializing, please wait..."
        elif self._state == AgentState.ERROR:
            return f"Agent initialization failed: {self._error}. Check Settings > Providers."
        return "Agent is not ready."
    
    async def initialize(self) -> bool:
        """
        Initialize or reinitialize the agent.
        
        Returns:
            True if agent is ready, False otherwise.
        """
        async with self._lock:
            self._state = AgentState.INITIALIZING
            self._error = None
            
            logger.info("Starting agent initialization...")
            
            try:
                # Check for valid API key
                api_key = self._get_api_key()
                if not api_key:
                    self._state = AgentState.UNINITIALIZED
                    logger.warning("No API key configured - agent uninitialized")
                    logger.info("To configure: run 'gigabot setup' or set API key in dashboard")
                    return False
                
                # Log key info (masked)
                key_preview = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
                logger.info(f"API key found: {key_preview}")
                
                # Create message bus if not provided
                if self._bus is None:
                    from nanobot.bus.queue import MessageBus
                    self._bus = MessageBus()
                    logger.debug("Created new MessageBus")
                
                # Create provider
                from nanobot.providers.litellm_provider import LiteLLMProvider
                
                provider_name = self._get_primary_provider() or "openrouter"
                api_base = self._get_api_base(provider_name)
                
                logger.info(f"Creating LLM provider: {provider_name}")
                logger.debug(f"API base: {api_base}")
                logger.debug(f"Default model: {self._config.agents.defaults.model}")
                
                self._provider = LiteLLMProvider(
                    api_key=api_key,
                    api_base=api_base,
                    default_model=self._config.agents.defaults.model,
                )
                
                # Create token tracker
                from nanobot.tracking.tokens import TokenTracker
                self._tracker = TokenTracker()
                logger.debug("Created TokenTracker")
                
                # Create agent loop
                from nanobot.agent.loop import AgentLoop
                
                logger.info("Creating AgentLoop...")
                self._agent = AgentLoop(
                    bus=self._bus,
                    provider=self._provider,
                    workspace=self._workspace,
                    model=self._config.agents.defaults.model,
                    config=self._config,
                    max_iterations=self._config.agents.defaults.max_iterations,
                    brave_api_key=self._config.providers.brave.api_key if hasattr(self._config.providers, 'brave') else None,
                )
                
                # Get session manager from agent
                self._sessions = self._agent.sessions
                
                # Update state
                self._state = AgentState.READY
                now = datetime.now()
                if self._initialized_at is None:
                    self._initialized_at = now
                self._last_reinit_at = now
                
                logger.info(f"Agent initialized successfully!")
                logger.info(f"  Provider: {provider_name}")
                logger.info(f"  Model: {self._config.agents.defaults.model}")
                logger.info(f"  Workspace: {self._workspace}")
                return True
                
            except Exception as e:
                self._state = AgentState.ERROR
                self._error = str(e)
                logger.error(f"Agent initialization failed: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                return False
    
    async def reinitialize(self) -> bool:
        """
        Force reinitialize the agent.
        
        Useful after config changes.
        """
        logger.info("Reinitializing agent...")
        return await self.initialize()
    
    async def handle_chat(self, message: str, session_id: str) -> str:
        """
        Handle a chat message.
        
        Args:
            message: User message
            session_id: Session identifier
            
        Returns:
            Agent response or error message
        """
        if not self.is_ready:
            return self.get_not_ready_message()
        
        try:
            # Process message through agent
            response = await self._process_message(message, session_id)
            return response
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error processing message: {e}"
    
    async def _process_message(self, message: str, session_id: str) -> str:
        """Process a message through the agent loop."""
        if self._agent is None:
            return "Agent not initialized"
        
        # Create inbound message
        from nanobot.bus.events import InboundMessage
        
        inbound = InboundMessage(
            channel="webui",
            sender_id=session_id,
            session_key=session_id,
            content=message,
        )
        
        # Put message on bus
        await self._bus.publish(inbound)
        
        # Process the message
        response = await self._agent._process_message(inbound)
        
        return response
    
    async def shutdown(self) -> None:
        """Shutdown the agent manager."""
        logger.info("Shutting down agent manager")
        self._agent = None
        self._state = AgentState.UNINITIALIZED
    
    def _has_api_key(self) -> bool:
        """Check if any API key is configured."""
        return self._get_api_key() is not None
    
    def _get_api_key(self) -> str | None:
        """Get the first available API key from config or environment."""
        import os
        
        providers = self._config.providers
        
        # Check each provider for API key in config
        if providers.openrouter.api_key:
            logger.debug("Found OpenRouter API key in config")
            return providers.openrouter.api_key
        if providers.anthropic.api_key:
            logger.debug("Found Anthropic API key in config")
            return providers.anthropic.api_key
        if providers.openai.api_key:
            logger.debug("Found OpenAI API key in config")
            return providers.openai.api_key
        if providers.moonshot.api_key:
            logger.debug("Found Moonshot API key in config")
            return providers.moonshot.api_key
        if providers.deepseek.api_key:
            logger.debug("Found DeepSeek API key in config")
            return providers.deepseek.api_key
        
        # Fallback: check environment variables
        env_keys = [
            ("OPENROUTER_API_KEY", "OpenRouter"),
            ("ANTHROPIC_API_KEY", "Anthropic"),
            ("OPENAI_API_KEY", "OpenAI"),
            ("MOONSHOT_API_KEY", "Moonshot"),
            ("DEEPSEEK_API_KEY", "DeepSeek"),
        ]
        
        for env_var, provider_name in env_keys:
            key = os.environ.get(env_var, "").strip()
            if key:
                logger.debug(f"Found {provider_name} API key in environment ({env_var})")
                return key
        
        logger.warning("No API key found in config or environment")
        return None
    
    def _get_primary_provider(self) -> str | None:
        """Get the name of the configured primary provider."""
        import os
        
        providers = self._config.providers
        
        # Return first configured provider from config
        if providers.openrouter.api_key:
            return "openrouter"
        if providers.anthropic.api_key:
            return "anthropic"
        if providers.openai.api_key:
            return "openai"
        if providers.moonshot.api_key:
            return "moonshot"
        if providers.deepseek.api_key:
            return "deepseek"
        
        # Fallback: check environment variables
        env_mapping = [
            ("OPENROUTER_API_KEY", "openrouter"),
            ("ANTHROPIC_API_KEY", "anthropic"),
            ("OPENAI_API_KEY", "openai"),
            ("MOONSHOT_API_KEY", "moonshot"),
            ("DEEPSEEK_API_KEY", "deepseek"),
        ]
        
        for env_var, provider_id in env_mapping:
            if os.environ.get(env_var, "").strip():
                return provider_id
        
        return None
    
    def _get_configured_providers(self) -> list[str]:
        """Get list of configured provider names."""
        configured = []
        providers = self._config.providers
        
        if providers.openrouter.api_key:
            configured.append("openrouter")
        if providers.anthropic.api_key:
            configured.append("anthropic")
        if providers.openai.api_key:
            configured.append("openai")
        if providers.moonshot.api_key:
            configured.append("moonshot")
        if providers.deepseek.api_key:
            configured.append("deepseek")
        
        return configured
    
    def _get_api_base(self, provider: str) -> str | None:
        """Get API base URL for a provider."""
        defaults = {
            "openrouter": "https://openrouter.ai/api/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "openai": "https://api.openai.com/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "glm": "https://open.bigmodel.cn/api/paas/v4",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "ollama": "http://localhost:11434/v1",
            "vllm": "http://localhost:8000/v1",
        }
        
        # Check if custom API base is configured
        provider_config = getattr(self._config.providers, provider, None)
        if provider_config and provider_config.api_base:
            return provider_config.api_base
        
        return defaults.get(provider)
