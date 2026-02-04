"""
API routes for GigaBot WebUI.

Provides REST endpoints for:
- Status and health
- Configuration management
- Session management
- Token tracking
- Gateway management
"""

from typing import Any, Callable, Coroutine
from pathlib import Path
import uuid
import asyncio

import httpx


def create_api_routes(
    config: Any = None,
    tracker: Any = None,
    sessions: Any = None,
    channels: Any = None,
    save_config: Callable[[], Coroutine[Any, Any, None]] | None = None,
    cron_service: Any = None,
) -> dict[str, Callable]:
    """
    Create API route handlers.
    
    Args:
        config: Configuration object.
        tracker: TokenTracker instance.
        sessions: SessionManager instance.
        channels: ChannelManager instance.
        save_config: Callback to save configuration.
        cron_service: CronService instance for scheduled jobs.
    
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
    
    # =====================
    # Provider Configuration APIs
    # =====================
    
    async def get_providers() -> dict[str, Any]:
        """Get provider configurations (keys masked)."""
        if not config:
            return {"providers": {}, "error": "No configuration"}
        
        providers_info = {}
        provider_names = ["openrouter", "anthropic", "openai", "moonshot", "deepseek", "glm", "qwen", "ollama", "vllm"]
        
        for name in provider_names:
            provider_config = getattr(config.providers, name, None)
            if provider_config:
                providers_info[name] = {
                    "has_key": bool(provider_config.api_key),
                    "api_base": provider_config.api_base,
                    "enabled": True,  # Providers are enabled if they have a key
                }
        
        return {"providers": providers_info}
    
    async def update_provider(provider_name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a provider's configuration."""
        if not config:
            return {"error": "No configuration"}
        
        provider_config = getattr(config.providers, provider_name, None)
        if not provider_config:
            return {"error": f"Unknown provider: {provider_name}"}
        
        # Update fields
        if "api_key" in data:
            provider_config.api_key = data["api_key"]
        if "api_base" in data:
            provider_config.api_base = data["api_base"]
        
        # Save config and trigger agent initialization if needed
        if save_config:
            await save_config()
        
        return {
            "success": True,
            "provider": provider_name,
            "has_key": bool(provider_config.api_key),
        }
    
    # =====================
    # Routing Configuration APIs
    # =====================
    
    async def get_routing() -> dict[str, Any]:
        """Get tiered routing configuration."""
        if not config:
            return {"error": "No configuration"}
        
        routing = config.agents.tiered_routing
        return {
            "enabled": routing.enabled,
            "fallback_tier": routing.fallback_tier,
            "tiers": {
                name: {
                    "models": tier.models,
                    "triggers": tier.triggers,
                }
                for name, tier in routing.tiers.items()
            } if routing.tiers else {},
        }
    
    async def update_routing(data: dict[str, Any]) -> dict[str, Any]:
        """Update routing configuration."""
        if not config:
            return {"error": "No configuration"}
        
        routing = config.agents.tiered_routing
        
        if "enabled" in data:
            routing.enabled = data["enabled"]
        if "fallback_tier" in data:
            routing.fallback_tier = data["fallback_tier"]
        if "tiers" in data:
            from nanobot.config.schema import TierConfig
            for tier_name, tier_data in data["tiers"].items():
                if tier_name in routing.tiers:
                    if "models" in tier_data:
                        routing.tiers[tier_name].models = tier_data["models"]
                    if "triggers" in tier_data:
                        routing.tiers[tier_name].triggers = tier_data["triggers"]
                else:
                    # Add new tier
                    routing.tiers[tier_name] = TierConfig(
                        models=tier_data.get("models", []),
                        triggers=tier_data.get("triggers", []),
                    )
        
        # Save config
        if save_config:
            await save_config()
        
        return {"success": True, "routing": await get_routing()}
    
    # =====================
    # Memory Configuration APIs
    # =====================
    
    async def get_memory_config() -> dict[str, Any]:
        """Get memory system configuration."""
        if not config:
            return {"error": "No configuration"}
        
        memory = config.agents.memory
        return {
            "enabled": memory.enabled,
            "vector_search": memory.vector_search,
            "context_memories": memory.context_memories,
        }
    
    async def update_memory_config(data: dict[str, Any]) -> dict[str, Any]:
        """Update memory configuration."""
        if not config:
            return {"error": "No configuration"}
        
        memory = config.agents.memory
        
        if "enabled" in data:
            memory.enabled = data["enabled"]
        if "vector_search" in data:
            memory.vector_search = data["vector_search"]
        if "context_memories" in data:
            memory.context_memories = data["context_memories"]
        
        # Save config
        if save_config:
            await save_config()
        
        return {"success": True, "memory": await get_memory_config()}
    
    # =====================
    # Team Configuration APIs
    # =====================
    
    async def get_team_config() -> dict[str, Any]:
        """Get team/swarm configuration."""
        if not config:
            return {"error": "No configuration"}
        
        team = config.agents.team
        swarm = config.agents.swarm
        
        return {
            "team": {
                "enabled": team.enabled,
                "qa_gate_enabled": team.qa_gate_enabled,
                "audit_gate_enabled": team.audit_gate_enabled,
                "audit_threshold": team.audit_threshold,
            },
            "swarm": {
                "enabled": swarm.enabled,
                "max_workers": swarm.max_workers,
                "worker_model": swarm.worker_model,
                "orchestrator_model": swarm.orchestrator_model,
            },
        }
    
    async def update_team_config(data: dict[str, Any]) -> dict[str, Any]:
        """Update team/swarm configuration."""
        if not config:
            return {"error": "No configuration"}
        
        if "team" in data:
            team = config.agents.team
            team_data = data["team"]
            if "enabled" in team_data:
                team.enabled = team_data["enabled"]
            if "qa_gate_enabled" in team_data:
                team.qa_gate_enabled = team_data["qa_gate_enabled"]
            if "audit_gate_enabled" in team_data:
                team.audit_gate_enabled = team_data["audit_gate_enabled"]
            if "audit_threshold" in team_data:
                team.audit_threshold = team_data["audit_threshold"]
        
        if "swarm" in data:
            swarm = config.agents.swarm
            swarm_data = data["swarm"]
            if "enabled" in swarm_data:
                swarm.enabled = swarm_data["enabled"]
            if "max_workers" in swarm_data:
                swarm.max_workers = swarm_data["max_workers"]
            if "worker_model" in swarm_data:
                swarm.worker_model = swarm_data["worker_model"]
            if "orchestrator_model" in swarm_data:
                swarm.orchestrator_model = swarm_data["orchestrator_model"]
        
        # Save config
        if save_config:
            await save_config()
        
        return {"success": True, "config": await get_team_config()}
    
    # =====================
    # Cron Jobs APIs
    # =====================
    
    def _serialize_cron_job(job: Any) -> dict[str, Any]:
        """Serialize a CronJob to a JSON-compatible dict."""
        return {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "schedule": {
                "kind": job.schedule.kind,
                "at_ms": job.schedule.at_ms,
                "every_ms": job.schedule.every_ms,
                "expr": job.schedule.expr,
                "tz": job.schedule.tz,
            },
            "payload": {
                "kind": job.payload.kind,
                "message": job.payload.message,
                "deliver": job.payload.deliver,
                "channel": job.payload.channel,
                "to": job.payload.to,
            },
            "state": {
                "next_run_at_ms": job.state.next_run_at_ms,
                "last_run_at_ms": job.state.last_run_at_ms,
                "last_status": job.state.last_status,
                "last_error": job.state.last_error,
            },
            "created_at_ms": job.created_at_ms,
            "updated_at_ms": job.updated_at_ms,
            "delete_after_run": job.delete_after_run,
        }
    
    async def get_cron_jobs() -> dict[str, Any]:
        """List all cron jobs."""
        if not cron_service:
            return {"jobs": [], "status": {"enabled": False}, "error": "Cron service not available"}
        
        jobs = cron_service.list_jobs(include_disabled=True)
        status = cron_service.status()
        
        return {
            "jobs": [_serialize_cron_job(j) for j in jobs],
            "status": status,
        }
    
    async def add_cron_job(data: dict[str, Any]) -> dict[str, Any]:
        """Add a new cron job."""
        if not cron_service:
            return {"error": "Cron service not available"}
        
        # Validate required fields
        name = data.get("name")
        message = data.get("message")
        schedule_data = data.get("schedule", {})
        
        if not name:
            return {"error": "Job name is required"}
        if not message:
            return {"error": "Job message is required"}
        
        # Build schedule
        from nanobot.cron.types import CronSchedule
        
        schedule_kind = schedule_data.get("kind", "every")
        schedule = CronSchedule(
            kind=schedule_kind,
            at_ms=schedule_data.get("at_ms"),
            every_ms=schedule_data.get("every_ms"),
            expr=schedule_data.get("expr"),
            tz=schedule_data.get("tz"),
        )
        
        # Validate schedule
        if schedule_kind == "every" and not schedule.every_ms:
            return {"error": "every_ms is required for 'every' schedule type"}
        if schedule_kind == "cron" and not schedule.expr:
            return {"error": "expr is required for 'cron' schedule type"}
        if schedule_kind == "at" and not schedule.at_ms:
            return {"error": "at_ms is required for 'at' schedule type"}
        
        job = cron_service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=data.get("deliver", False),
            channel=data.get("channel"),
            to=data.get("to"),
            delete_after_run=data.get("delete_after_run", False),
        )
        
        return {"success": True, "job": _serialize_cron_job(job)}
    
    async def run_cron_job(job_id: str, force: bool = False) -> dict[str, Any]:
        """Manually run a cron job."""
        if not cron_service:
            return {"error": "Cron service not available"}
        
        # Check if job exists
        jobs = cron_service.list_jobs(include_disabled=True)
        job = next((j for j in jobs if j.id == job_id), None)
        
        if not job:
            return {"error": f"Job not found: {job_id}"}
        
        success = await cron_service.run_job(job_id, force=force)
        
        if success:
            # Refresh job state
            jobs = cron_service.list_jobs(include_disabled=True)
            job = next((j for j in jobs if j.id == job_id), None)
            return {"success": True, "job": _serialize_cron_job(job) if job else None}
        else:
            return {"error": "Job is disabled. Use force=true to run anyway."}
    
    async def update_cron_job(job_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a cron job (enable/disable)."""
        if not cron_service:
            return {"error": "Cron service not available"}
        
        # Check if job exists
        jobs = cron_service.list_jobs(include_disabled=True)
        job = next((j for j in jobs if j.id == job_id), None)
        
        if not job:
            return {"error": f"Job not found: {job_id}"}
        
        # Currently only supports enable/disable
        if "enabled" in data:
            updated_job = cron_service.enable_job(job_id, enabled=data["enabled"])
            if updated_job:
                return {"success": True, "job": _serialize_cron_job(updated_job)}
        
        return {"success": True, "job": _serialize_cron_job(job)}
    
    async def delete_cron_job(job_id: str) -> dict[str, Any]:
        """Delete a cron job."""
        if not cron_service:
            return {"error": "Cron service not available"}
        
        success = cron_service.remove_job(job_id)
        
        if success:
            return {"success": True, "deleted_id": job_id}
        else:
            return {"error": f"Job not found: {job_id}"}
    
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
        # Provider management
        "providers": get_providers,
        "update_provider": update_provider,
        # Routing configuration
        "routing": get_routing,
        "update_routing": update_routing,
        # Memory configuration
        "memory_config": get_memory_config,
        "update_memory_config": update_memory_config,
        # Team configuration
        "team_config": get_team_config,
        "update_team_config": update_team_config,
        # Cron Jobs
        "cron_jobs": get_cron_jobs,
        "add_cron_job": add_cron_job,
        "run_cron_job": run_cron_job,
        "update_cron_job": update_cron_job,
        "delete_cron_job": delete_cron_job,
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
