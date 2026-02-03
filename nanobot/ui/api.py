"""
API routes for GigaBot WebUI.

Provides REST endpoints for:
- Status and health
- Configuration management
- Session management
- Token tracking
- Gateway management
"""

from typing import Any, Callable
from pathlib import Path
import uuid
import asyncio

import httpx


def create_api_routes(
    config: Any = None,
    tracker: Any = None,
    sessions: Any = None,
    channels: Any = None,
    save_config: Callable | None = None,
) -> dict[str, Callable]:
    """
    Create API route handlers.
    
    Args:
        config: Configuration object.
        tracker: TokenTracker instance.
        sessions: SessionManager instance.
        channels: ChannelManager instance.
    
    Returns:
        Dictionary of route handlers.
    """
    
    async def get_status() -> dict[str, Any]:
        """Get system status."""
        status = {
            "status": "running",
            "version": "0.1.0",
        }
        
        if config:
            status["model"] = config.agents.defaults.model
            status["workspace"] = str(config.workspace_path)
        
        if channels:
            status["channels"] = channels.get_status()
        
        if tracker:
            status["tracking"] = tracker.get_summary()
        
        return status
    
    async def get_config() -> dict[str, Any]:
        """Get configuration (sanitized)."""
        if not config:
            return {"error": "No configuration"}
        
        # Return safe config without secrets
        return {
            "agents": {
                "model": config.agents.defaults.model,
                "max_tokens": config.agents.defaults.max_tokens,
                "tiered_routing": config.agents.tiered_routing.enabled,
            },
            "channels": {
                name: {
                    "enabled": getattr(config.channels, name).enabled
                }
                for name in ["telegram", "whatsapp", "discord", "signal", "matrix"]
                if hasattr(config.channels, name)
            },
            "security": {
                "auth_mode": config.security.auth.mode,
                "sandbox_mode": config.security.sandbox.mode,
            },
        }
    
    async def get_sessions() -> dict[str, Any]:
        """Get session list."""
        if not sessions:
            return {"sessions": []}
        
        session_list = sessions.list_sessions()
        result = []
        
        for s in session_list:
            # Handle both Session objects and dicts
            if isinstance(s, dict):
                result.append({
                    "key": s.get("key", "unknown"),
                    "message_count": len(s.get("messages", [])),
                    "last_updated": s.get("updated_at"),
                })
            else:
                result.append({
                    "key": getattr(s, "key", "unknown"),
                    "message_count": len(getattr(s, "messages", [])),
                    "last_updated": s.updated_at.isoformat() if hasattr(s, "updated_at") else None,
                })
        
        return {"sessions": result}
    
    async def get_tracking() -> dict[str, Any]:
        """Get token tracking stats."""
        if not tracker:
            return {"error": "Tracking not enabled"}
        
        return tracker.get_summary()
    
    async def get_channels() -> dict[str, Any]:
        """Get channel status."""
        if not channels:
            return {"channels": {}}
        
        return {"channels": channels.get_status()}
    
    async def get_memory_stats() -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "daily_notes": 0,
            "long_term_entries": 0,
            "vector_store_size": 0,
        }
    
    # =====================
    # Gateway Management APIs
    # =====================
    
    async def get_gateways() -> dict[str, Any]:
        """List all configured gateways with status."""
        if not config:
            return {"gateways": [], "error": "No configuration"}
        
        gateways = config.providers.gateways.gateways
        return {
            "gateways": [
                {
                    "id": g.id,
                    "name": g.name,
                    "provider": g.provider,
                    "enabled": g.enabled,
                    "is_primary": g.is_primary,
                    "is_fallback": g.is_fallback,
                    "priority": g.priority,
                    "health_status": g.health_status,
                    "last_error": g.last_error,
                    "failure_count": g.failure_count,
                    "has_api_key": bool(g.api_key),
                    "api_base": g.api_base,
                }
                for g in gateways
            ],
            "cooldown_seconds": config.providers.gateways.cooldown_seconds,
            "max_retries": config.providers.gateways.max_retries,
        }
    
    async def add_gateway(data: dict[str, Any]) -> dict[str, Any]:
        """Add a new gateway."""
        if not config:
            return {"error": "No configuration"}
        
        from nanobot.config.schema import LLMGatewayConfig
        
        # Generate unique ID
        gateway_id = data.get("id") or str(uuid.uuid4())[:8]
        
        # If this is set as primary, unset any existing primary
        if data.get("is_primary"):
            for g in config.providers.gateways.gateways:
                g.is_primary = False
        
        new_gateway = LLMGatewayConfig(
            id=gateway_id,
            name=data.get("name", f"{data.get('provider', 'gateway').title()} Gateway"),
            provider=data.get("provider", "openrouter"),
            api_key=data.get("api_key", ""),
            api_base=data.get("api_base"),
            enabled=data.get("enabled", True),
            is_primary=data.get("is_primary", False),
            is_fallback=data.get("is_fallback", False),
            priority=data.get("priority", len(config.providers.gateways.gateways)),
            health_status="unknown",
        )
        
        config.providers.gateways.gateways.append(new_gateway)
        
        # Save config if save function provided
        if save_config:
            await save_config()
        
        return {
            "success": True,
            "gateway": {
                "id": new_gateway.id,
                "name": new_gateway.name,
                "provider": new_gateway.provider,
                "enabled": new_gateway.enabled,
                "is_primary": new_gateway.is_primary,
            }
        }
    
    async def update_gateway(gateway_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing gateway."""
        if not config:
            return {"error": "No configuration"}
        
        # Find the gateway
        gateway = None
        for g in config.providers.gateways.gateways:
            if g.id == gateway_id:
                gateway = g
                break
        
        if not gateway:
            return {"error": f"Gateway not found: {gateway_id}"}
        
        # If setting as primary, unset any existing primary
        if data.get("is_primary") and not gateway.is_primary:
            for g in config.providers.gateways.gateways:
                g.is_primary = False
        
        # Update fields
        if "name" in data:
            gateway.name = data["name"]
        if "api_key" in data:
            gateway.api_key = data["api_key"]
        if "api_base" in data:
            gateway.api_base = data["api_base"]
        if "enabled" in data:
            gateway.enabled = data["enabled"]
        if "is_primary" in data:
            gateway.is_primary = data["is_primary"]
        if "is_fallback" in data:
            gateway.is_fallback = data["is_fallback"]
        if "priority" in data:
            gateway.priority = data["priority"]
        
        # Save config if save function provided
        if save_config:
            await save_config()
        
        return {
            "success": True,
            "gateway": {
                "id": gateway.id,
                "name": gateway.name,
                "provider": gateway.provider,
                "enabled": gateway.enabled,
                "is_primary": gateway.is_primary,
                "is_fallback": gateway.is_fallback,
            }
        }
    
    async def delete_gateway(gateway_id: str) -> dict[str, Any]:
        """Delete a gateway."""
        if not config:
            return {"error": "No configuration"}
        
        # Find and remove the gateway
        gateways = config.providers.gateways.gateways
        for i, g in enumerate(gateways):
            if g.id == gateway_id:
                del gateways[i]
                
                # Save config if save function provided
                if save_config:
                    await save_config()
                
                return {"success": True, "deleted_id": gateway_id}
        
        return {"error": f"Gateway not found: {gateway_id}"}
    
    async def test_gateway(gateway_id: str) -> dict[str, Any]:
        """Test gateway connectivity."""
        if not config:
            return {"error": "No configuration"}
        
        # Find the gateway
        gateway = None
        for g in config.providers.gateways.gateways:
            if g.id == gateway_id:
                gateway = g
                break
        
        if not gateway:
            return {"error": f"Gateway not found: {gateway_id}"}
        
        if not gateway.api_key:
            return {"error": "Gateway has no API key configured"}
        
        # Test connectivity based on provider
        try:
            api_base = gateway.api_base or _get_default_api_base(gateway.provider)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try a simple models list request
                headers = {
                    "Authorization": f"Bearer {gateway.api_key}",
                    "Content-Type": "application/json",
                }
                
                # Different providers have different endpoints
                if gateway.provider in ["openrouter", "openai", "moonshot", "deepseek", "qwen", "glm"]:
                    url = f"{api_base}/models"
                elif gateway.provider == "anthropic":
                    # Anthropic doesn't have a models endpoint, use a minimal completion
                    url = f"{api_base or 'https://api.anthropic.com'}/v1/messages"
                    headers["x-api-key"] = gateway.api_key
                    headers["anthropic-version"] = "2023-06-01"
                    # Just check if we get a valid error (means API key works)
                    response = await client.post(
                        url,
                        headers=headers,
                        json={"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": []}
                    )
                    # If we get a 400 (bad request) instead of 401 (unauthorized), the key works
                    if response.status_code in [200, 400]:
                        gateway.health_status = "healthy"
                        gateway.failure_count = 0
                        gateway.last_error = None
                        return {"success": True, "status": "healthy", "message": "Gateway connected"}
                    elif response.status_code == 401:
                        gateway.health_status = "unhealthy"
                        gateway.last_error = "Invalid API key"
                        return {"success": False, "status": "unhealthy", "error": "Invalid API key"}
                else:
                    url = f"{api_base}/models"
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    gateway.health_status = "healthy"
                    gateway.failure_count = 0
                    gateway.last_error = None
                    return {"success": True, "status": "healthy", "message": "Gateway connected"}
                else:
                    gateway.health_status = "unhealthy"
                    gateway.last_error = f"HTTP {response.status_code}"
                    return {"success": False, "status": "unhealthy", "error": f"HTTP {response.status_code}"}
                    
        except httpx.TimeoutException:
            gateway.health_status = "unhealthy"
            gateway.last_error = "Connection timeout"
            return {"success": False, "status": "unhealthy", "error": "Connection timeout"}
        except Exception as e:
            gateway.health_status = "unhealthy"
            gateway.last_error = str(e)
            return {"success": False, "status": "unhealthy", "error": str(e)}
    
    return {
        "status": get_status,
        "config": get_config,
        "sessions": get_sessions,
        "tracking": get_tracking,
        "channels": get_channels,
        "memory": get_memory_stats,
        # Gateway management
        "gateways": get_gateways,
        "add_gateway": add_gateway,
        "update_gateway": update_gateway,
        "delete_gateway": delete_gateway,
        "test_gateway": test_gateway,
    }


def _get_default_api_base(provider: str) -> str:
    """Get default API base URL for a provider."""
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
    return defaults.get(provider, "https://api.openai.com/v1")


class APIClient:
    """
    Client for GigaBot API.
    
    Can be used by external applications to interact with GigaBot.
    """
    
    def __init__(self, base_url: str, auth_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        data: dict | None = None
    ) -> dict:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response.json()
    
    async def get_status(self) -> dict:
        """Get system status."""
        return await self.request("GET", "/api/status")
    
    async def chat(self, message: str, session_id: str = "api:default") -> str:
        """Send a chat message."""
        response = await self.request("POST", "/api/chat", {
            "message": message,
            "session_id": session_id,
        })
        return response.get("response", "")
    
    async def get_sessions(self) -> list:
        """Get session list."""
        response = await self.request("GET", "/api/sessions")
        return response.get("sessions", [])
    
    async def get_tracking(self) -> dict:
        """Get tracking stats."""
        return await self.request("GET", "/api/tracking")
