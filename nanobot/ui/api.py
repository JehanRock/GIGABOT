"""
API routes for GigaBot WebUI.

Provides REST endpoints for:
- Status and health
- Configuration management
- Session management
- Token tracking
"""

from typing import Any, Callable
from pathlib import Path

import httpx


def create_api_routes(
    config: Any = None,
    tracker: Any = None,
    sessions: Any = None,
    channels: Any = None,
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
    
    return {
        "status": get_status,
        "config": get_config,
        "sessions": get_sessions,
        "tracking": get_tracking,
        "channels": get_channels,
        "memory": get_memory_stats,
    }


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
