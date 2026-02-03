"""LiteLLM provider implementation for multi-provider support."""

import os
import json
import time
from typing import Any, AsyncIterator
from dataclasses import dataclass, field

import litellm
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""
    content: str = ""
    is_tool_call: bool = False
    tool_call_id: str = ""
    tool_call_name: str = ""
    tool_call_arguments: str = ""
    finish_reason: str = ""
    is_final: bool = False


@dataclass
class ProviderHealth:
    """Health status of a provider/model."""
    healthy: bool = True
    last_failure: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0
    last_error: str = ""
    
    def mark_failed(self, error: str, cooldown_seconds: int = 300) -> None:
        """Mark as failed and start cooldown."""
        self.healthy = False
        self.last_failure = time.time()
        self.failure_count += 1
        self.cooldown_until = time.time() + cooldown_seconds
        self.last_error = error
    
    def mark_success(self) -> None:
        """Mark as healthy after successful call."""
        self.healthy = True
        self.failure_count = 0
        self.last_error = ""
    
    def is_available(self) -> bool:
        """Check if available (healthy or cooldown expired)."""
        if self.healthy:
            return True
        return time.time() >= self.cooldown_until


@dataclass
class GatewayInfo:
    """Runtime information about a configured gateway."""
    id: str
    name: str
    provider: str
    api_key: str
    api_base: str | None
    is_primary: bool
    is_fallback: bool
    priority: int
    health: ProviderHealth = field(default_factory=ProviderHealth)


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Moonshot, DeepSeek, GLM,
    and many other providers through a unified interface.
    
    Features:
    - Automatic provider detection from model name
    - Model failover with health tracking
    - Usage tracking
    - Cost estimation
    """
    
    # Provider configurations
    PROVIDER_CONFIGS = {
        "openrouter": {
            "env_key": "OPENROUTER_API_KEY",
            "prefix": "openrouter/",
            "api_base": "https://openrouter.ai/api/v1",
        },
        "anthropic": {
            "env_key": "ANTHROPIC_API_KEY",
            "prefix": "",
        },
        "openai": {
            "env_key": "OPENAI_API_KEY",
            "prefix": "",
        },
        "moonshot": {
            "env_key": "MOONSHOT_API_KEY",
            "prefix": "openai/",  # OpenAI-compatible
            "api_base": "https://api.moonshot.cn/v1",
        },
        "deepseek": {
            "env_key": "DEEPSEEK_API_KEY",
            "prefix": "deepseek/",
            "api_base": "https://api.deepseek.com/v1",
        },
        "glm": {
            "env_key": "GLM_API_KEY",
            "prefix": "openai/",  # OpenAI-compatible
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
        },
        "qwen": {
            "env_key": "QWEN_API_KEY",
            "prefix": "openai/",  # OpenAI-compatible
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "ollama": {
            "env_key": "",
            "prefix": "ollama/",
            "api_base": "http://localhost:11434",
        },
        "vllm": {
            "env_key": "OPENAI_API_KEY",
            "prefix": "hosted_vllm/",
        },
    }
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        fallback_models: list[str] | None = None,
        cooldown_seconds: int = 300,
        gateways_config: Any | None = None,  # LLMGatewaysConfig
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.fallback_models = fallback_models or []
        self.cooldown_seconds = cooldown_seconds
        
        # Health tracking (per model)
        self._model_health: dict[str, ProviderHealth] = {}
        
        # Gateway tracking (for multi-gateway support)
        self._gateways: list[GatewayInfo] = []
        self._gateway_cooldown = cooldown_seconds
        self._gateway_max_retries = 3
        
        # Initialize gateways from config
        if gateways_config:
            self._init_gateways(gateways_config)
        
        # Usage tracking
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._request_count = 0
        
        # Detect provider type
        self._detected_provider = self._detect_provider(default_model, api_key, api_base)
        
        # Configure environment
        self._configure_environment(api_key, api_base)
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
    
    def _init_gateways(self, gateways_config: Any) -> None:
        """Initialize gateways from configuration."""
        self._gateway_cooldown = gateways_config.cooldown_seconds
        self._gateway_max_retries = gateways_config.max_retries
        
        for gw in gateways_config.gateways:
            if gw.enabled:
                self._gateways.append(GatewayInfo(
                    id=gw.id,
                    name=gw.name,
                    provider=gw.provider,
                    api_key=gw.api_key,
                    api_base=gw.api_base,
                    is_primary=gw.is_primary,
                    is_fallback=gw.is_fallback,
                    priority=gw.priority,
                    health=ProviderHealth(),
                ))
        
        # Sort gateways: primary first, then by priority
        self._gateways.sort(key=lambda g: (not g.is_primary, g.priority))
    
    def _get_ordered_gateways(self) -> list[GatewayInfo]:
        """Get gateways in order: primary first, then fallbacks by priority."""
        # Primary gateway first
        primary = [g for g in self._gateways if g.is_primary and g.health.is_available()]
        
        # Then fallback gateways by priority
        fallbacks = sorted(
            [g for g in self._gateways if g.is_fallback and not g.is_primary and g.health.is_available()],
            key=lambda g: g.priority
        )
        
        return primary + fallbacks
    
    def _get_gateway_by_id(self, gateway_id: str) -> GatewayInfo | None:
        """Get a gateway by ID."""
        for gw in self._gateways:
            if gw.id == gateway_id:
                return gw
        return None
    
    def _detect_provider(
        self, 
        model: str, 
        api_key: str | None, 
        api_base: str | None
    ) -> str:
        """Detect provider from model name, key, or base URL."""
        model_lower = model.lower()
        
        # Check by API key prefix
        if api_key:
            if api_key.startswith("sk-or-"):
                return "openrouter"
            if api_key.startswith("sk-ant-"):
                return "anthropic"
        
        # Check by API base
        if api_base:
            if "openrouter" in api_base:
                return "openrouter"
            if "moonshot" in api_base:
                return "moonshot"
            if "deepseek" in api_base:
                return "deepseek"
            if "bigmodel" in api_base:
                return "glm"
            if "dashscope" in api_base:
                return "qwen"
            if "localhost" in api_base or "127.0.0.1" in api_base:
                if "11434" in api_base:
                    return "ollama"
                return "vllm"
        
        # Check by model name prefix
        if model_lower.startswith("moonshot/") or "kimi" in model_lower:
            return "moonshot"
        if model_lower.startswith("deepseek/"):
            return "deepseek"
        if model_lower.startswith("glm/") or "zhipu" in model_lower:
            return "glm"
        if model_lower.startswith("qwen/"):
            return "qwen"
        if model_lower.startswith("ollama/"):
            return "ollama"
        if "claude" in model_lower or model_lower.startswith("anthropic/"):
            return "anthropic"
        if "gpt" in model_lower or model_lower.startswith("openai/"):
            return "openai"
        
        # Default to OpenRouter for unknown
        if api_key:
            return "openrouter"
        
        return "anthropic"
    
    def _configure_environment(self, api_key: str | None, api_base: str | None) -> None:
        """Configure environment variables for LiteLLM."""
        if not api_key:
            return
        
        provider_config = self.PROVIDER_CONFIGS.get(self._detected_provider, {})
        env_key = provider_config.get("env_key", "OPENAI_API_KEY")
        
        if env_key:
            os.environ.setdefault(env_key, api_key)
        
        # Also set OpenAI key for OpenAI-compatible providers
        if self._detected_provider in ["moonshot", "deepseek", "glm", "qwen", "vllm"]:
            os.environ.setdefault("OPENAI_API_KEY", api_key)
    
    def _format_model_name(self, model: str) -> str:
        """Format model name for LiteLLM based on provider."""
        # Detect provider for this specific model
        provider = self._detect_provider(model, None, None)
        config = self.PROVIDER_CONFIGS.get(provider, {})
        
        # Apply prefix if needed
        prefix = config.get("prefix", "")
        if prefix and not model.startswith(prefix) and "/" not in model:
            model = f"{prefix}{model}"
        
        # Special handling for OpenRouter
        if provider == "openrouter" or self._detected_provider == "openrouter":
            if not model.startswith("openrouter/"):
                model = f"openrouter/{model}"
        
        return model
    
    def _get_api_base_for_model(self, model: str) -> str | None:
        """Get API base URL for a specific model."""
        if self.api_base:
            return self.api_base
        
        provider = self._detect_provider(model, None, None)
        config = self.PROVIDER_CONFIGS.get(provider, {})
        return config.get("api_base")
    
    def _get_model_health(self, model: str) -> ProviderHealth:
        """Get or create health tracking for a model."""
        if model not in self._model_health:
            self._model_health[model] = ProviderHealth()
        return self._model_health[model]
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM with failover support.
        
        Supports both gateway-level and model-level fallback:
        - If gateways are configured, tries each gateway in order (primary first, then fallbacks)
        - Within each gateway, uses the configured model
        - Falls back to model-level fallback if no gateways configured
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = model or self.default_model
        last_error = ""
        
        # Try gateway-level fallback first if gateways are configured
        if self._gateways:
            ordered_gateways = self._get_ordered_gateways()
            
            for gateway in ordered_gateways:
                try:
                    response = await self._call_model_with_gateway(
                        gateway, model, messages, tools, max_tokens, temperature
                    )
                    
                    # Success - mark healthy and return
                    gateway.health.mark_success()
                    self._request_count += 1
                    
                    # Track usage
                    if response.usage:
                        self._total_tokens += response.usage.get("total_tokens", 0)
                        self._prompt_tokens += response.usage.get("prompt_tokens", 0)
                        self._completion_tokens += response.usage.get("completion_tokens", 0)
                    
                    return response
                    
                except Exception as e:
                    last_error = str(e)
                    gateway.health.mark_failed(last_error, self._gateway_cooldown)
                    continue
            
            # All gateways failed
            return LLMResponse(
                content=f"Error: All gateways failed. Last error: {last_error}",
                finish_reason="error",
            )
        
        # Fall back to model-level failover (original behavior)
        # Build list of models to try (primary + fallbacks)
        models_to_try = [model] + [
            fb for fb in self.fallback_models if fb != model
        ]
        
        for try_model in models_to_try:
            health = self._get_model_health(try_model)
            
            # Skip unhealthy models
            if not health.is_available():
                continue
            
            try:
                response = await self._call_model(
                    try_model, messages, tools, max_tokens, temperature
                )
                
                # Success - mark healthy and return
                health.mark_success()
                self._request_count += 1
                
                # Track usage
                if response.usage:
                    self._total_tokens += response.usage.get("total_tokens", 0)
                    self._prompt_tokens += response.usage.get("prompt_tokens", 0)
                    self._completion_tokens += response.usage.get("completion_tokens", 0)
                
                return response
                
            except Exception as e:
                last_error = str(e)
                health.mark_failed(last_error, self.cooldown_seconds)
                continue
        
        # All models failed
        return LLMResponse(
            content=f"Error: All models failed. Last error: {last_error}",
            finish_reason="error",
        )
    
    async def _call_model_with_gateway(
        self,
        gateway: GatewayInfo,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Make an API call using a specific gateway."""
        # Determine the model to use based on gateway provider
        formatted_model = self._format_model_for_gateway(model, gateway)
        
        # Get API base from gateway or default for provider
        api_base = gateway.api_base or self.PROVIDER_CONFIGS.get(gateway.provider, {}).get("api_base")
        
        kwargs: dict[str, Any] = {
            "model": formatted_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "api_key": gateway.api_key,
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await acompletion(**kwargs)
        return self._parse_response(response)
    
    def _format_model_for_gateway(self, model: str, gateway: GatewayInfo) -> str:
        """Format model name for a specific gateway."""
        provider = gateway.provider
        config = self.PROVIDER_CONFIGS.get(provider, {})
        
        # Apply prefix based on gateway provider
        prefix = config.get("prefix", "")
        
        # Special handling for OpenRouter - always use openrouter/ prefix
        if provider == "openrouter":
            if not model.startswith("openrouter/"):
                return f"openrouter/{model}"
            return model
        
        # For OpenAI-compatible providers
        if prefix and provider in ["moonshot", "glm", "qwen"]:
            # Strip any existing provider prefix and use openai/
            model_name = model.split("/")[-1] if "/" in model else model
            return f"openai/{model_name}"
        
        # For DeepSeek, Ollama, etc.
        if prefix and not model.startswith(prefix) and "/" not in model:
            return f"{prefix}{model}"
        
        return model
    
    async def _call_model(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Make a single API call to a model."""
        formatted_model = self._format_model_name(model)
        api_base = self._get_api_base_for_model(model)
        
        kwargs: dict[str, Any] = {
            "model": formatted_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await acompletion(**kwargs)
        return self._parse_response(response)
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
    
    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        stats = {
            "total_tokens": self._total_tokens,
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "request_count": self._request_count,
            "model_health": {
                model: {
                    "healthy": health.healthy,
                    "failure_count": health.failure_count,
                    "available": health.is_available(),
                    "last_error": health.last_error,
                }
                for model, health in self._model_health.items()
            },
        }
        
        # Include gateway health if configured
        if self._gateways:
            stats["gateway_health"] = {
                gw.id: {
                    "name": gw.name,
                    "provider": gw.provider,
                    "is_primary": gw.is_primary,
                    "is_fallback": gw.is_fallback,
                    "healthy": gw.health.healthy,
                    "failure_count": gw.health.failure_count,
                    "available": gw.health.is_available(),
                    "last_error": gw.health.last_error,
                }
                for gw in self._gateways
            }
        
        return stats
    
    def get_gateway_status(self) -> list[dict[str, Any]]:
        """Get status of all configured gateways."""
        return [
            {
                "id": gw.id,
                "name": gw.name,
                "provider": gw.provider,
                "is_primary": gw.is_primary,
                "is_fallback": gw.is_fallback,
                "priority": gw.priority,
                "health_status": "healthy" if gw.health.healthy else "unhealthy",
                "available": gw.health.is_available(),
                "failure_count": gw.health.failure_count,
                "last_error": gw.health.last_error,
            }
            for gw in self._gateways
        ]
    
    def add_gateway(
        self,
        id: str,
        name: str,
        provider: str,
        api_key: str,
        api_base: str | None = None,
        is_primary: bool = False,
        is_fallback: bool = False,
        priority: int = 0,
    ) -> None:
        """Add a gateway at runtime."""
        # If setting as primary, unset any existing primary
        if is_primary:
            for gw in self._gateways:
                gw.is_primary = False
        
        self._gateways.append(GatewayInfo(
            id=id,
            name=name,
            provider=provider,
            api_key=api_key,
            api_base=api_base,
            is_primary=is_primary,
            is_fallback=is_fallback,
            priority=priority,
            health=ProviderHealth(),
        ))
        
        # Re-sort gateways
        self._gateways.sort(key=lambda g: (not g.is_primary, g.priority))
    
    def remove_gateway(self, gateway_id: str) -> bool:
        """Remove a gateway at runtime."""
        for i, gw in enumerate(self._gateways):
            if gw.id == gateway_id:
                del self._gateways[i]
                return True
        return False
    
    def update_gateway(self, gateway_id: str, **kwargs) -> bool:
        """Update a gateway's configuration."""
        gw = self._get_gateway_by_id(gateway_id)
        if not gw:
            return False
        
        # If setting as primary, unset any existing primary
        if kwargs.get("is_primary") and not gw.is_primary:
            for g in self._gateways:
                g.is_primary = False
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(gw, key):
                setattr(gw, key, value)
        
        # Re-sort gateways
        self._gateways.sort(key=lambda g: (not g.is_primary, g.priority))
        return True
    
    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._request_count = 0
    
    def add_fallback_model(self, model: str) -> None:
        """Add a fallback model."""
        if model not in self.fallback_models:
            self.fallback_models.append(model)
    
    def remove_fallback_model(self, model: str) -> None:
        """Remove a fallback model."""
        if model in self.fallback_models:
            self.fallback_models.remove(model)
    
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        """
        Send a streaming chat completion request.
        
        Yields tokens as they arrive from the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Yields:
            StreamChunk objects with content or tool call data.
        """
        model = model or self.default_model
        
        # Build list of models to try (primary + fallbacks)
        models_to_try = [model] + [
            fb for fb in self.fallback_models if fb != model
        ]
        
        for try_model in models_to_try:
            health = self._get_model_health(try_model)
            
            # Skip unhealthy models
            if not health.is_available():
                continue
            
            try:
                async for chunk in self._stream_model(
                    try_model, messages, tools, max_tokens, temperature
                ):
                    yield chunk
                
                # Success - mark healthy
                health.mark_success()
                self._request_count += 1
                return
                
            except Exception as e:
                health.mark_failed(str(e), self.cooldown_seconds)
                continue
        
        # All models failed
        yield StreamChunk(
            content="Error: All models failed",
            is_final=True,
            finish_reason="error",
        )
    
    async def _stream_model(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from a single model."""
        formatted_model = self._format_model_name(model)
        api_base = self._get_api_base_for_model(model)
        
        kwargs: dict[str, Any] = {
            "model": formatted_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await acompletion(**kwargs)
        
        # Track accumulated tool calls
        tool_calls: dict[int, dict[str, str]] = {}
        accumulated_content = ""
        
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            
            delta = choice.delta if hasattr(choice, "delta") else None
            if not delta:
                continue
            
            # Handle content
            if hasattr(delta, "content") and delta.content:
                accumulated_content += delta.content
                yield StreamChunk(content=delta.content)
            
            # Handle tool calls
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    
                    if hasattr(tc, "function"):
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments
            
            # Check for finish
            if hasattr(choice, "finish_reason") and choice.finish_reason:
                # Yield any accumulated tool calls
                for tc_data in tool_calls.values():
                    yield StreamChunk(
                        is_tool_call=True,
                        tool_call_id=tc_data["id"],
                        tool_call_name=tc_data["name"],
                        tool_call_arguments=tc_data["arguments"],
                    )
                
                # Final chunk
                yield StreamChunk(
                    is_final=True,
                    finish_reason=choice.finish_reason,
                )
                
                # Track usage if available
                if hasattr(chunk, "usage") and chunk.usage:
                    self._total_tokens += getattr(chunk.usage, "total_tokens", 0)
                    self._prompt_tokens += getattr(chunk.usage, "prompt_tokens", 0)
                    self._completion_tokens += getattr(chunk.usage, "completion_tokens", 0)
                
                return
